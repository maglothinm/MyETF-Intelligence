"""Immutable intents, fresh send-time decisions and restart-safe channel receipts."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Mapping

from .opportunity_common import OpportunityError, DataUnavailable, digest, timestamp, utc
from .opportunity_engine import evaluate, membership
from .opportunity_significance import normalize
from .opportunity_state import event


class DeliveryRejected(Exception):
    """Provider definitely rejected submission; a later validated retry is permitted."""


def authorize(record: Mapping | None, environment: Mapping, now: datetime) -> dict:
    if not record or record.get('version') != 1 or record.get('repository_id') != 1349678672:
        raise OpportunityError('live mode requires an explicit canonical activation record')
    if environment.get('POLITITRACK_MODE') != 'production' or environment.get('CLOUD_RUN_JOB') != record.get('runtime_job') or environment.get('POLITITRACK_OPPORTUNITY_OWNER') != 'runtime_v2_ai':
        raise OpportunityError('live mode requires the existing authorized Runtime v2 AI writer')
    if record.get('runtime_job') != 'polititrack-ai' or not record.get('approved_by') or not record.get('approval_reference'):
        raise OpportunityError('activation record is incomplete')
    if not timestamp(record.get('cutoff')) or not timestamp(record.get('approved_at')) or timestamp(record['cutoff']) > now or timestamp(record['approved_at']) > now:
        raise OpportunityError('activation timestamps are invalid')
    if not isinstance(record.get('channels'), list) or not set(record['channels']) <= {'pushover','gmail'}:
        raise OpportunityError('activation channel scope is invalid')
    return {**dict(record), 'activation_id':digest(record)}


def format_alert(intent: Mapping, current: Mapping, dashboard_url: str) -> dict:
    market = current['market']
    label = 'Invalidated' if intent['transition'] == 'invalidation' else 'Potential opportunity for review'
    routes = ', '.join(sorted({r['route'].replace('_',' ') for r in current['entry_significance']['routes']})) or 'prior qualified buying'
    quote = market.get('quote') or {}
    amount = current['significance']['buy_range']
    path = str(market.get('path','unknown')).replace('_',' ')
    return {'title':f"PolitiTrack — {current['ticker']}: {label}",
            'message':f"{label}. {routes}. Disclosed buying range: {amount['lower'] or 'unknown'} to {amount['upper'] or 'open/unknown'} {current.get('currency') or ''}. "
                      f"Price path: {path}. Quote {quote.get('price','unavailable')} at {quote.get('at','unknown')} ({market.get('session','unknown')}). "
                      f"Evidence: {current['evidence_status']}. Reasons: {', '.join(current['reason_codes']) or 'all required gates passed'}. "
                      "Entry ceases to qualify if price, freshness, required data or evidence gates fail. No return is promised.",
            'url':dashboard_url.rstrip('/')+'/current-opportunities.html#'+current['opportunity_id']}


def deliver(state: dict, rules: Mapping, *, clock, calendar, market_provider, evidence_provider, provider,
            checkpoint, raw_rows, activation: Mapping, environment: Mapping, configured_channels: list[str], dashboard_url: str) -> None:
    """Checkpoint must durably commit the existing AI snapshot before returning.

    Before submission a channel is *uncertain*, never merely in-memory pending.
    Process death at any send boundary therefore cannot cause a blind retry.
    """
    if rules['mode'] != 'live' or state['mode'] != 'live':
        return
    authorized = authorize(activation, environment, clock())
    if state.get('activation') != authorized:
        raise OpportunityError('delivery activation does not match the persisted baseline')
    allowed = set(configured_channels) & set(authorized['channels'])
    count = 0
    for eid, intent in list(state['intents'].items()):
        if intent['mode'] != 'live':
            continue
        for channel in intent['channels']:
            delivery = state['deliveries'][eid][channel]
            if delivery['status'] not in ('pending','failed','deferred') or count >= rules['delivery_budget']:
                continue
            if channel not in allowed:
                delivery.update(status='deferred', reason='channel_not_authorized')
                event(state, 'delivery_state', {'event_id':eid, 'channel':channel, **delivery}, clock())
                checkpoint(state)
                continue
            now = clock()
            history, _ = normalize(raw_rows(), now)
            prior = state['opportunities'].get(intent['opportunity_id'])
            rows = [r for r in history if prior and r['security_key'] == prior['security_key']]
            reason = None
            if not rows or not prior or membership(rows) != intent['snapshot']['membership_hash'] or prior['rule_hash'] != rules['method_hash']:
                reason = 'membership_or_method_superseded'
            elif prior['notification_event_ids'] and prior['notification_event_ids'][-1] != eid:
                reason = 'newer_notification_supersedes_intent'
            if reason is None:
                try:
                    market = market_provider.snapshot(rows, now, force=True)
                    evidence = evidence_provider.review(rows, membership(rows), clock(), force=True)
                except DataUnavailable as exc:
                    market, evidence = {'gap':str(exc)}, {'status':'incomplete', 'reason':str(exc)}
                current = evaluate(state, rows, history, market, evidence, rules, clock(), calendar, channels=sorted(allowed), input_cutoff=now)
                # Revalidation can invalidate the opportunity; that decision is durable even if nothing is sent.
                expected = 'invalidated' if intent['transition'] == 'invalidation' else 'opportunity_available'
                if current['lifecycle'] != expected:
                    reason = 'delivery_gates_failed'
                if current['notification_event_ids'] and current['notification_event_ids'][-1] != eid:
                    reason = 'newer_notification_supersedes_intent'
                if timestamp(current['evaluation_cutoff']) < timestamp(intent['queued_at']):
                    reason = 'evaluation_precedes_intent'
                event(state, 'delivery_validation', {'event_id':eid, 'channel':channel, 'evaluation_id':current['evaluation_id'], 'valid':reason is None, 'reason':reason}, clock())
                checkpoint(state)
            else:
                current = prior
            if reason:
                delivery.update(status='superseded', reason=reason)
                event(state, 'delivery_state', {'event_id':eid, 'channel':channel, **delivery}, clock())
                checkpoint(state)
                continue
            # A fresh authorization and freshness check at the last boundary after persistence.
            authorize(activation, environment, clock())
            qtime = timestamp(current['market'].get('quote',{}).get('at'))
            if intent['transition'] != 'invalidation' and (not qtime or (clock()-qtime).total_seconds() > rules['quote_max_seconds'] or not calendar.regular(clock()) or clock() > timestamp(current['evidence']['valid_until'])):
                delivery.update(status='deferred', reason='expired_during_checkpoint')
                event(state, 'delivery_state', {'event_id':eid, 'channel':channel, **delivery}, clock())
                checkpoint(state)
                continue
            count += 1
            delivery.update(status='uncertain', attempts=delivery['attempts']+1, attempted_at=utc(clock()), reason='submission_may_have_been_accepted')
            event(state, 'delivery_state', {'event_id':eid, 'channel':channel, **delivery}, clock())
            checkpoint(state)  # External side effect is forbidden before this durable boundary.
            if intent['transition'] != 'invalidation' and ((clock()-qtime).total_seconds() > rules['quote_max_seconds'] or not calendar.regular(clock()) or clock() > timestamp(current['evidence']['valid_until'])):
                delivery.update(status='deferred', reason='expired_during_submission_checkpoint')
                event(state, 'delivery_state', {'event_id':eid, 'channel':channel, **delivery}, clock())
                checkpoint(state)
                continue
            try:
                receipt = provider.send(channel, format_alert(intent, current, dashboard_url), eid)
            except DeliveryRejected:
                delivery.update(status='failed', reason='provider_rejected_before_acceptance')
            except Exception:
                delivery.update(status='uncertain', reason='provider_acceptance_unknown')
            else:
                if receipt and receipt.get('accepted') is True:
                    delivery.update(status='accepted', accepted_at=utc(clock()), reason=None, receipt=deepcopy(receipt))
                else:
                    delivery.update(status='uncertain', reason='provider_acceptance_unknown')
            event(state, 'delivery_state', {'event_id':eid, 'channel':channel, **delivery}, clock())
            checkpoint(state)
