"""Case-level guards; never rewrite the retained disclosure ledger."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Mapping


AUTOMATIC = re.compile(
    r'dividend\s+reinvest|automatic\s+reinvest|\bDRIP\b|automatic\s+investment|'
    r'vesting|restricted\s+stock\s+(?:award|unit)|stock\s+grant|'
    r'(?:managed|discretionary)\s+(?:by|account)|investment\s+manager', re.I)
DIRECTIONS = re.compile(r'\b(P|S|E)\s+(\d{2}/\d{2}/\d{4})\b')
TICKERS = re.compile(r'\(([A-Z][A-Z0-9.\-]{0,9})\)\s*\[(?:ST|OP|OT)\]')


def issues(row: Mapping) -> list[str]:
    """Return specific uncertainty/error reasons, not inferred corrected trades."""
    reasons: list[str] = []
    raw = str(row.get('raw_row') or '')
    text = ' '.join(str(row.get(k) or '') for k in
                    ('raw_row', 'comments', 'comment', 'description', 'asset',
                     'transaction_intent', 'notes'))
    if row.get('transaction_type') == 'Purchase' and AUTOMATIC.search(text):
        reasons.append('automatic_or_managed_purchase_not_discretionary_evidence')
    if row.get('asset_type') in ('Stock Option', 'Option', 'Bond', 'Municipal Bond'):
        reasons.append('not_verified_common_stock')
    if re.search(r'\[(?:OP|GS|CB)\]', raw) and row.get('equity_like') is True:
        reasons.append('security_type_conflicts_with_source')
    directions = DIRECTIONS.findall(raw)
    expected = 'P' if row.get('transaction_type') == 'Purchase' else 'S' if str(row.get('transaction_type')).startswith('Sale') else 'E'
    if len(directions) > 1:
        reasons.append('multiple_source_transaction_rows')
    if directions and any(d != expected for d, _ in directions):
        reasons.append('source_direction_conflict')
    if len(directions) == 1:
        try:
            source_date = datetime.strptime(directions[0][1], '%m/%d/%Y').date().isoformat()
            if source_date != row.get('transaction_date'):
                reasons.append('source_transaction_date_conflict')
        except ValueError:
            reasons.append('invalid_source_transaction_date')
    source_owner = re.match(r'^\s*(SP|JT|DC)\s+', raw)
    if source_owner and row.get('owner') != {'SP':'Spouse', 'JT':'Joint', 'DC':'Dependent Child'}[source_owner[1]]:
        reasons.append('source_owner_conflict')
    symbols = set(TICKERS.findall(raw))
    if len(symbols) > 1:
        reasons.append('multiple_source_security_symbols')
    if symbols and str(row.get('ticker') or '') not in symbols:
        reasons.append('source_ticker_conflict')
    if raw and row.get('source') == 'senate':
        # A Senate HTML row retains explicit pipe-separated direction and ticker.
        cells = [s.strip() for s in raw.split('|')]
        directions_in_cells = [s for s in cells if s in ('Purchase', 'Sale', 'Sale (Partial)', 'Sale (Full)', 'Exchange')]
        if directions_in_cells and any(s != row.get('transaction_type') for s in directions_in_cells):
            reasons.append('source_direction_conflict')
    amount = str(row.get('amount') or '')
    bounds = re.findall(r'\$\s*(\d[\d,]*(?:\.\d+)?)', amount)
    try:
        if len(bounds) == 2 and Decimal(bounds[0].replace(',', '')) > Decimal(bounds[1].replace(',', '')):
            reasons.append('inverted_disclosed_amount_range')
        if 'amount_lower' in row and 'amount_upper' in row and row['amount_upper'] is not None and row['amount_lower'] is not None:
            if Decimal(str(row['amount_lower'])) > Decimal(str(row['amount_upper'])):
                reasons.append('inverted_disclosed_amount_range')
    except (InvalidOperation, ValueError):
        reasons.append('invalid_disclosed_amount')
    return sorted(set(reasons))
