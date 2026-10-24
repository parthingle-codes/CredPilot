"""Unit tests for the in-process AI rate limiter."""

from __future__ import annotations

from app.rate_limit import SlidingWindowLimiter


def test_limiter_allows_requests_up_to_the_limit() -> None:
    limiter = SlidingWindowLimiter(2, window_seconds=10)

    assert limiter.allow("client", now=0) == (True, 0)
    assert limiter.allow("client", now=1) == (True, 0)


def test_limiter_blocks_and_reports_retry_after() -> None:
    limiter = SlidingWindowLimiter(2, window_seconds=10)

    limiter.allow("client", now=0)
    limiter.allow("client", now=1)
    allowed, retry_after = limiter.allow("client", now=2)

    assert allowed is False
    assert retry_after == 9


def test_limiter_window_slides() -> None:
    limiter = SlidingWindowLimiter(2, window_seconds=10)

    limiter.allow("client", now=0)
    limiter.allow("client", now=1)
    assert limiter.allow("client", now=2)[0] is False

    # At t=11 both old events are outside the window.
    assert limiter.allow("client", now=11) == (True, 0)


def test_limiter_keys_are_independent() -> None:
    limiter = SlidingWindowLimiter(1, window_seconds=10)

    assert limiter.allow("a", now=0)[0] is True
    assert limiter.allow("b", now=0)[0] is True
    assert limiter.allow("a", now=1)[0] is False


def test_limiter_enforces_minimums() -> None:
    limiter = SlidingWindowLimiter(0, window_seconds=0)
    assert limiter.limit == 1
    assert limiter.window_seconds == 1.0
    assert limiter.allow("x", now=0)[0] is True
    assert limiter.allow("x", now=0.1)[0] is False
