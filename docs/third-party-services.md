# Third-Party Services

Most third-party providers haven't been selected/integrated yet — this table is filled in as each integration boundary is reached, per the project rule that credential-requiring decisions stop for explicit user input rather than being assumed.

| Provider | Purpose | Data Shared | Retention | Required? | Status |
|---|---|---|---|---|---|
| AI provider — [OpenRouter](https://openrouter.ai) | NL food parsing, AI coach | Parsing: the free-text food description only. Coach: the message plus structured app data already scoped to the requesting user (today's dashboard, recent weight, recent workout sessions) — never email, name, password, or tokens (see `ai-safety.md`) | Per OpenRouter's and the underlying model provider's policy — not yet independently verified; do not treat this as confirmed until reviewed before production launch | Optional — every AI endpoint returns a clear 503 with `AI_API_KEY` unset, and the rest of the app is unaffected | **Selected, requires `AI_API_KEY`** — see `.env.example`. Default model is a free-tier OpenRouter model (`nvidia/nemotron-3.5-lightning:free`); free-tier model availability changes over time, check `openrouter.ai/models?max_price=0` before relying on it long-term |
| Food database | Nutrition search/lookup, barcode lookup | Food search query / barcode only | Provider policy | Core to full nutrition search, but manual/custom food entry works without it | Not yet selected |
| Object storage | Food/progress/profile photos | User-uploaded images only, private buckets, signed URLs | Until user deletion or account deletion | Optional (photo features are optional) | Not yet selected |
| Email provider | Verification, password reset | Email address, transactional content only | Provider policy | Core if email auth is used | Not yet selected |
| Analytics (if added) | Product analytics | Minimal telemetry, never raw health data by default | Provider policy | Optional | Not yet added |
| Hosting / database host | Application + DB hosting | All application data (encrypted at rest) | Per hosting/backup policy | Core | Not yet selected |

## Process for adding a provider

1. Confirm the provider is actually necessary for the feature being built.
2. Review the provider's data-processing / privacy terms.
3. Fill in this table with the real answer, not a placeholder.
4. Add the required environment variables to `.env.example` (as names/placeholders only).
5. Update `privacy-policy.md` and `ai-safety.md` if the provider touches user data or AI processing.
6. Verify the provider's terms before production launch (§35/§36 of the master prompt) — final compliance determination requires qualified legal counsel.

This file must be kept accurate — it is referenced directly by the Privacy Policy.
