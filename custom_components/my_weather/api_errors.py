"""HTTP status policy for Meteonomiqs API-key failover."""

RETRY_WITH_OTHER_KEY = frozenset((401, 403, 429))


def should_try_other_key(status: int) -> bool:
    """Only authentication/authorization/rate limit statuses trigger key rotation."""
    return status in RETRY_WITH_OTHER_KEY
