"""Narrow integrations into the hardened analyst and its existing Runtime v2 owner."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from .opportunity_common import STATE_NAME, OpportunityError, load_rules, read_json, utc, timestamp, write_bytes
from .opportunity_engine import cycle
from .opportunity_market import ExchangeCalendar
from .opportunity_notifications import authorize, deliver
from .opportunity_providers import EvidenceProvider, MarketProvider, NotificationProvider, RequestBudget, capabilities, enrich_identities
from .opportunity_state import load, save, validate_directory, event
from .opportunity_evidence import SourceReviewer
from .collector_freshness import nonproduction_evidence


def read_history(config, *, now=None, max_hours=24) -> list[dict]:
    """Read every retained observed revision; no latest-only AI/Edge upstream filter."""
    rows = []
    for directory in (config.legislative_dir, config.executive_dir):
        if directory is None:
            continue
        # Required source state is fatal; absence of an optional ledger is not an empty successful source.
        source = read_json(directory / 'state.json')
        success = timestamp(source.get('last_success_utc'))
        if not success:
            raise OpportunityError('required collector successful state is unavailable')
        if now and (success > now or (now-success).total_seconds() > max_hours*3600):
            raise OpportunityError('required collector source coverage is stale')
        for name in ('transactions.jsonl','purchases.jsonl'):
            path = directory / name
            if path.exists():
                for line in path.read_text(encoding='utf-8').splitlines():
                    if line.strip():
                        try:
                            value = json.loads(line, parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
                            if not isinstance(value, dict):
                                raise ValueError('non-object')
                            if not nonproduction_evidence(value):
                                rows.append(value)
                        except ValueError as exc:
                            raise OpportunityError('corrupt required transaction history') from exc
    return rows


class OpportunityRuntime:
    def __init__(self, config, rules, *, clock=None, environment=None):
        self.config, self.rules = config, rules
        self.clock = clock or (lambda:datetime.now(timezone.utc))
        self.environment = dict(os.environ if environment is None else environment)
        self.state = load(config.ai_dir, self.clock())
        self.activation = None
        if rules['mode'] == 'live':
            if self.environment.get('OPPORTUNITY_MODE') != 'live':
                raise OpportunityError('live mode additionally requires explicit OPPORTUNITY_MODE=live')
            self.activation = authorize(read_json(config.ai_dir / 'opportunity-activation.json'), self.environment, self.clock())
        # Malformed retained optional records remain a state-integrity failure.
        self.edge_predecessors = {}
        for name in ('investor-edge-observations.json','investor-edge-profiles.json','investor-edge-leaderboard.json'):
            path = config.ai_dir / name
            if path.exists():
                read_json(path)
                self.edge_predecessors[name] = path.read_bytes()

    def evaluate(self, session, *, market_provider=None, evidence_provider=None, calendar=None):
        from . import ai_filing_analyst as analyst
        caps = capabilities(self.config.ai_dir, self.clock())
        budget = RequestBudget(self.rules['request_budget'])
        market = market_provider or MarketProvider(self.config, self.rules, session, caps, self.clock, budget)
        reviews = [r['evidence'] for r in self.state['opportunities'].values() if r.get('evidence')]
        evidence = evidence_provider or EvidenceProvider(reviews, self.rules,
            reviewer=SourceReviewer(self.config, self.rules, market, caps, self.clock),
            model_budget=self.rules['evidence_model_budget'])
        channels = analyst._requested_candidate_channels(self.config) if self.rules['mode'] == 'live' else ['simulation']
        if self.activation:
            channels = sorted(set(channels) & set(self.activation['channels']))
        cycle(self.state, enrich_identities(read_history(self.config, now=self.clock(), max_hours=self.rules['evidence_max_hours']), caps, self.clock()), self.rules, self.clock,
              calendar or ExchangeCalendar(), market, evidence, channels=channels, activation=self.activation)
        self.state['telemetry']['provider_requests_remaining'] = budget.remaining
        self.state['telemetry']['provider_capability_verified'] = bool(caps)
        save(self.config.ai_dir, self.state)
        return self.state['telemetry']

    def restore_edge_after_failure(self):
        """Optional enrichment may fail without publishing a partly changed Edge record."""
        for name, payload in self.edge_predecessors.items():
            write_bytes(self.config.ai_dir / name, payload)
        for name in ('investor-edge-observations.json','investor-edge-profiles.json','investor-edge-leaderboard.json'):
            path = self.config.ai_dir / name
            if name not in self.edge_predecessors and path.exists():
                path.unlink()  # Only a newly created optional Edge output from this attempt.


def prepare(config) -> OpportunityRuntime | None:
    path = os.environ.get('OPPORTUNITY_RULES_PATH')
    rules = load_rules(Path(path) if path else None, mode=os.environ.get('OPPORTUNITY_MODE'))
    validate_directory(config.ai_dir)
    if rules['mode'] == 'off' and (config.ai_dir / STATE_NAME).exists():
        now = datetime.now(timezone.utc)
        state = load(config.ai_dir, now, migrate=False)
        if state['mode'] != 'off':
            state['mode'] = 'off'
            event(state, 'mode_change', {'mode':'off', 'reason':'configured_rollback'}, now)
            save(config.ai_dir, state)
    return None if rules['mode'] == 'off' else OpportunityRuntime(config, rules)


def analyst_config(command: list[str], environment: dict):
    """Parse the exact child invocation with its environment, then restore the parent.

    JobRunner is a single-threaded command process; no provider call occurs inside
    this brief environment scope.
    """
    from . import ai_filing_analyst as analyst
    original = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(environment)
        return analyst.build_config(analyst.build_parser().parse_args(command[2:]))
    finally:
        os.environ.clear()
        os.environ.update(original)


def deliver_runtime(config, environment, checkpoint, *, clock=None, market_provider=None, evidence_provider=None, provider=None, calendar=None):
    """Called only by JobRunner under its AI writer lock, after a successful analyst."""
    from . import ai_filing_analyst as analyst
    clock = clock or (lambda:datetime.now(timezone.utc))
    rules = load_rules(Path(environment['OPPORTUNITY_RULES_PATH']) if environment.get('OPPORTUNITY_RULES_PATH') else None, mode=environment.get('OPPORTUNITY_MODE'))
    if rules['mode'] != 'live' or config.suppress_alerts:
        return
    state = load(config.ai_dir, clock(), migrate=False)
    if state is None:
        raise OpportunityError('live delivery has no migrated opportunity state')
    activation = read_json(config.ai_dir / 'opportunity-activation.json')
    caps = capabilities(config.ai_dir, clock())
    session = analyst.build_session('PolitiTrack Current Opportunity')
    market = market_provider or MarketProvider(config, rules, session, caps, clock, RequestBudget(rules['request_budget']))
    evidence = evidence_provider or EvidenceProvider([r['evidence'] for r in state['opportunities'].values()], rules,
        reviewer=SourceReviewer(config, rules, market, caps, clock), model_budget=rules['evidence_model_budget'])
    def commit(value):
        save(config.ai_dir, value)
        checkpoint()
    # Persist evaluated intents through the same durable owner before any provider call.
    commit(state)
    deliver(state, rules, clock=clock, calendar=calendar or ExchangeCalendar(), market_provider=market,
            evidence_provider=evidence, provider=provider or NotificationProvider(config), checkpoint=commit,
            raw_rows=lambda:enrich_identities(read_history(config, now=clock(), max_hours=rules['evidence_max_hours']), caps, clock()), activation=activation,
            environment=environment, configured_channels=analyst._requested_candidate_channels(config), dashboard_url=config.dashboard_url)
