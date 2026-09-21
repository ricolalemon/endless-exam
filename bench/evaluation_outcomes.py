"""Separate unavailable evaluations from scored model responses.

Historical attempts are immutable. These helpers give their corrected scoring
interpretation without changing or discarding their raw evidence.
"""

INFRASTRUCTURE_FAILURES = frozenset({
    'transport_error', 'network_error', 'connection_error', 'server_error',
    'quota', 'rate_limit', 'missing_usage', 'incomplete_turn', 'cli_error',
    'malformed_event', 'collector_error', 'verification_process_failed',
    'independent_verifier_disagreement',
})


def infrastructure_reason(row):
    for key in ('error', 'finish_reason', 'verify_msg'):
        value = row.get(key)
        if isinstance(value, str) and value in INFRASTRUCTURE_FAILURES:
            return value
    return None


def scored_view(row):
    """Return null validity/objective for unavailable evaluations, never zero."""
    reason = infrastructure_reason(row)
    if reason:
        return {**row, 'evaluation_status': 'infrastructure_failure',
                'scored': False, 'feasible': None, 'objective': None,
                'infrastructure_reason': reason}
    return {**row, 'evaluation_status': 'scored', 'scored': True}


def require_scored(row):
    """Refuse to silently zero or drop missing calls from a fixed-cohort score."""
    reason = infrastructure_reason(row)
    if reason or row.get('scored') is False:
        identity = '/'.join(str(row.get(k, '?')) for k in ('model', 'config', 'family', 'seed'))
        raise ValueError(f'Unscored infrastructure failure: {identity} ({reason}). '
                         'Collect the missing evaluation before reporting its cohort score.')
    return row
