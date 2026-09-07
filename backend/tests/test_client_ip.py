import pytest
from starlette.datastructures import Headers
from starlette.requests import Request

from app.core.client_ip import UNKNOWN_CLIENT, resolve_client_ip

PROXY = "10.0.0.1"
REAL_CLIENT = "203.0.113.7"
ATTACKER_CLAIM = "9.9.9.9"


def _request(*, peer: str | None = PROXY, forwarded: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": Headers(raw=headers).raw,
        "client": (peer, 12345) if peer else None,
    }
    return Request(scope)


# --- no proxy configured --------------------------------------------------


def test_without_a_configured_proxy_the_peer_address_is_used() -> None:
    request = _request(peer=REAL_CLIENT)

    assert resolve_client_ip(request, trusted_proxy_count=0) == REAL_CLIENT


def test_a_spoofed_header_is_ignored_when_no_proxy_is_configured() -> None:
    """The default has to be safe: an app exposed directly must not let a
    caller pick their own rate-limit bucket by sending a header."""
    request = _request(peer=REAL_CLIENT, forwarded=ATTACKER_CLAIM)

    assert resolve_client_ip(request, trusted_proxy_count=0) == REAL_CLIENT


def test_a_missing_peer_is_reported_rather_than_crashing() -> None:
    request = _request(peer=None)

    assert resolve_client_ip(request, trusted_proxy_count=0) == UNKNOWN_CLIENT


# --- one proxy ------------------------------------------------------------


def test_with_one_proxy_the_forwarded_client_is_used() -> None:
    """The bug this fixes: without it every user behind the proxy shares a
    single bucket, so one abusive client locks out everyone."""
    request = _request(peer=PROXY, forwarded=REAL_CLIENT)

    assert resolve_client_ip(request, trusted_proxy_count=1) == REAL_CLIENT


def test_a_client_cannot_spoof_its_way_out_of_rate_limiting() -> None:
    """The reason the value is read from the RIGHT of the chain.

    An attacker sends their own X-Forwarded-For; the proxy appends their real
    address after it. Reading from the right skips whatever they prepended,
    so they cannot mint a fresh identity per request.
    """
    request = _request(peer=PROXY, forwarded=f"{ATTACKER_CLAIM}, {REAL_CLIENT}")

    assert resolve_client_ip(request, trusted_proxy_count=1) == REAL_CLIENT


def test_a_long_spoofed_chain_still_resolves_to_the_real_client() -> None:
    spoofed = ", ".join(f"9.9.9.{i}" for i in range(20))
    request = _request(peer=PROXY, forwarded=f"{spoofed}, {REAL_CLIENT}")

    assert resolve_client_ip(request, trusted_proxy_count=1) == REAL_CLIENT


def test_whitespace_in_the_chain_is_tolerated() -> None:
    request = _request(peer=PROXY, forwarded=f"  {ATTACKER_CLAIM} ,  {REAL_CLIENT}  ")

    assert resolve_client_ip(request, trusted_proxy_count=1) == REAL_CLIENT


# --- two proxies ----------------------------------------------------------


def test_with_two_proxies_the_client_is_two_from_the_right() -> None:
    """client -> CDN -> nginx -> app. The CDN appends the client, nginx
    appends the CDN."""
    request = _request(peer=PROXY, forwarded=f"{REAL_CLIENT}, 198.51.100.5")

    assert resolve_client_ip(request, trusted_proxy_count=2) == REAL_CLIENT


def test_two_proxies_with_a_spoofed_prefix() -> None:
    request = _request(
        peer=PROXY, forwarded=f"{ATTACKER_CLAIM}, {REAL_CLIENT}, 198.51.100.5"
    )

    assert resolve_client_ip(request, trusted_proxy_count=2) == REAL_CLIENT


# --- misconfiguration -----------------------------------------------------


def test_a_missing_header_falls_back_to_the_peer_address() -> None:
    """Configured for a proxy but nothing set the header — probably a request
    that bypassed it. The peer is the only value here that isn't
    client-supplied."""
    request = _request(peer=PROXY, forwarded=None)

    assert resolve_client_ip(request, trusted_proxy_count=1) == PROXY


def test_an_empty_header_falls_back_to_the_peer_address() -> None:
    request = _request(peer=PROXY, forwarded="   ")

    assert resolve_client_ip(request, trusted_proxy_count=1) == PROXY


def test_a_chain_shorter_than_configured_is_not_trusted() -> None:
    """Configured for two proxies but only one entry arrived: the chain isn't
    what the operator described, so nothing in it is believable. Falling back
    to the peer is worse for accuracy and better for safety."""
    request = _request(peer=PROXY, forwarded=ATTACKER_CLAIM)

    assert resolve_client_ip(request, trusted_proxy_count=2) == PROXY


@pytest.mark.parametrize("count", [0, -1, -5])
def test_non_positive_counts_never_read_the_header(count: int) -> None:
    request = _request(peer=PROXY, forwarded=ATTACKER_CLAIM)

    assert resolve_client_ip(request, trusted_proxy_count=count) == PROXY
