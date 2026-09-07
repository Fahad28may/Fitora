"""Version stamp for the user-facing legal documents.

Consent records store the version a user actually saw, so bump this whenever
`docs/privacy-policy.md`, `docs/terms-of-service.md`, or
`docs/health-disclaimer.md` change in a way that affects what someone is
agreeing to. It lives in code rather than config because a policy change is a
code change -- an operator should not be able to silently re-stamp consent.
"""

POLICY_VERSION = "2026-09-07-draft"

__all__ = ["POLICY_VERSION"]
