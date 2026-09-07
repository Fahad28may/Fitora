from starlette.requests import Request

from app.core.config import get_settings

UNKNOWN_CLIENT = "unknown"


def resolve_client_ip(request: Request, *, trusted_proxy_count: int) -> str:
    """The caller's real IP, for rate limiting.

    Behind a proxy, `request.client.host` is the *proxy*, so every user lands
    in one rate-limit bucket and a single abusive client locks everyone out.
    The fix is `X-Forwarded-For` — but trusting it naively is worse than the
    bug it fixes, because the header is client-supplied: an attacker could
    send a fresh fake IP on every request and never be limited at all.

    So the header is only consulted when the operator has said how many
    proxies actually sit in front of the app, and the value is taken by
    counting from the RIGHT of the chain. Each proxy appends the address it
    received the connection from, so the rightmost entries are the ones our
    own infrastructure wrote. Anything a client prepends shifts the left end
    of the list and cannot move the position we read.

    Worked example with `trusted_proxy_count=1`:

    - Honest client: proxy appends the real IP -> `"1.2.3.4"` -> we read
      `1.2.3.4`.
    - Attacker sends `X-Forwarded-For: 9.9.9.9`: the proxy appends their real
      IP after it -> `"9.9.9.9, 1.2.3.4"` -> we still read `1.2.3.4`.

    `trusted_proxy_count=0` (the default) ignores the header entirely, which
    is correct for local development and for an app exposed directly.

    Set the count to the *exact* number of proxies. Too low and users share a
    bucket; too high and the position read falls into client-controlled
    territory, which is the spoofing hole this exists to close.
    """
    direct_peer = request.client.host if request.client else UNKNOWN_CLIENT

    if trusted_proxy_count <= 0:
        return direct_peer

    forwarded = request.headers.get("x-forwarded-for", "")
    chain = [part.strip() for part in forwarded.split(",") if part.strip()]
    if not chain:
        # Configured for a proxy but none set the header — likely a direct
        # request that bypassed it. The peer address is the only thing here
        # that isn't client-supplied.
        return direct_peer

    index = len(chain) - trusted_proxy_count
    if index < 0:
        # Fewer entries than configured proxies: the chain is not what the
        # operator described, so nothing in it is safe to believe.
        return direct_peer
    return chain[index]


def client_ip_key(request: Request) -> str:
    """slowapi key function. Reads config per request so tests (and a
    re-read of settings) see changes without re-importing this module."""
    return resolve_client_ip(
        request, trusted_proxy_count=get_settings().trusted_proxy_count
    )


__all__ = ["UNKNOWN_CLIENT", "client_ip_key", "resolve_client_ip"]
