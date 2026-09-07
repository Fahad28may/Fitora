# AI Safety & Architecture

**Implemented (Phase 3):** NL food parsing (`POST /ai/parse-food`), a single-thread AI coach (`POST /ai/coach/messages`, `GET /ai/coach/messages`, `DELETE /ai/coach/messages`), and AI-proposed mutating actions via a **propose → confirm** flow (`POST /ai/actions/propose`, `POST /ai/actions/confirm`) for `log_weight`, `log_water`, and `log_food`. All via [OpenRouter](https://openrouter.ai). See `app/services/ai/`.

**Not implemented:** additional action tools (`create_workout`, `create_meal`, goal edits), photo food recognition, barcode-triggered AI. The **coach itself still cannot take actions** — it is read-only/advisory and its system prompt says so; mutating actions live only behind the separate, explicitly-confirmed `/ai/actions/*` endpoints, never inside a coach reply.

## Architecture

```text
User → /ai/actions/propose → Backend → Retrieve authorized user data
     → AI proposes ONE structured action (never executes) → Backend validates against a
       fixed action allow-list + per-action Pydantic bounds → proposal returned to user
User reviews & confirms → /ai/actions/confirm → Backend re-validates (no AI) → Database
```

The model only ever *proposes*. Nothing is written during `propose`. The write happens only in `confirm`, which calls no AI, takes `user_id` from the authenticated session, and re-validates every parameter with the same business-rule bounds as the manual endpoints. This is the concrete realization of the "User confirmation (if mutating)" step below.

```text
User → AI request → Backend → Validate request → Retrieve authorized user data
     → AI → Structured response → Backend validation → User confirmation (if mutating)
     → Database
```

The LLM never talks to the database, never receives raw credentials, and never executes arbitrary code or SQL. Today it:

1. Receives a system prompt plus **structured, minimum-necessary application data** the backend has already fetched and authorized for the requesting user (today's dashboard, recent weight, recent workout sessions for the coach; nothing beyond the raw text for parsing).
2. Returns plain text (coach) or a JSON array validated against a Pydantic schema (parsing) — never a tool call, since none exist yet.

## Tools

Built (behind propose → confirm):

```text
log_weight(user_id: from session, weight_kg)
log_water(user_id: from session, amount_ml)
log_food(user_id: from session, food_id, quantity, unit, meal_category)
```

Not built yet: `create_workout`, `create_meal`, goal edits.

The rules, enforced for every built tool (see `app/services/ai/action_service.py` and `tests/test_ai_actions.py`):

- `user_id` is always taken from the authenticated session, never from AI output.
- Inputs are Pydantic-validated exactly like a normal API request — the model's proposed parameters are re-validated at `confirm` against the same bounds as the manual endpoints (e.g. weight 0–500 kg, water 0–5000 ml), so the AI can never produce a value a user couldn't enter by hand.
- The action set is a fixed allow-list; anything the model returns outside it becomes `none` (nothing to execute).
- Every mutating action requires an explicit user `confirm` call before it commits; `propose` performs no writes at all.
- `log_food` reuses the manual food-diary service, so its ownership check (a user cannot log another user's private food) applies unchanged — covered by `test_confirm_cannot_log_another_users_private_food`.

The AI must never be able to: access another user's data, execute arbitrary SQL, bypass application permissions, retrieve secrets, modify security settings, modify billing information, or access arbitrary files. This holds by construction — the write path (`confirm`) never calls the model, and the model can only ever return one of a fixed set of proposals for the requesting user's own data.

## Prompt injection defense

User-provided text (food-parse input, coach messages, and anything embedded in the structured context like food/workout names) is **untrusted input**, always passed to the model as delimited data, never concatenated into system instructions.

Layers actually implemented:

- Fixed system prompts (`food_parser_service.py`, `coach_service.py`, `action_service.py`) that explicitly state user content is data, not instructions, and instruct the model to keep parsing/discussing/mapping even if the input looks like a command aimed at it.
- Structured JSON output requested for parsing and for action proposals, validated with Pydantic (`ParsedFoodItem`, `RawProposal` + per-action params); free text is only accepted for the coach's conversational replies.
- Input length limits (`FoodParseRequest.text` ≤ 1000 chars, `CoachMessageCreateRequest.message` ≤ 2000 chars, `ActionProposeRequest.message` ≤ 1000 chars).
- Output validation after the model responds (schema for parsing/actions; a non-empty, length-capped string for the coach) before anything is shown to the user or stored.
- A successful injection still can't mutate data: the action write path (`/ai/actions/confirm`) calls no model and requires explicit user confirmation, and even a coerced proposal is re-validated against a fixed allow-list with per-action bounds before the user ever sees a confirm button.

This defends against the *architecture* being exploitable; it does not by itself guarantee any specific free model actually resists injection attempts in practice — that depends on the underlying model and hasn't been adversarially tested against a live provider.

## Output validation pipeline

**Food parsing:** `LLM → JSON array → Pydantic schema validation → one retry with a corrective prompt on failure → 422 to the user if still invalid`. Parsed items are matched against the food database for the user to pick from — nothing is ever auto-logged.

**Coach:** the reply is required to be non-empty and is truncated to 4000 characters; there's no retry loop since free-text conversational replies don't have a structural schema to validate against.

Malformed AI output is never executed against the database — there's no execution path for it to reach in either feature.

## What data goes to AI providers

| Feature | Data sent | Why | Retained by provider? | Used for training? |
|---|---|---|---|---|
| NL food parsing | The food-log text only (e.g. "two eggs and a roti") | Extract structured food items | Per OpenRouter/model-provider policy — not yet independently verified, see `third-party-services.md` | Not confirmed — do not assume "no" without checking the specific model's terms before production |
| AI coach | The message, plus structured JSON: today's dashboard (calorie/macro/water progress), last 5 weight entries, last 3 workout sessions' start times/notes, and up to the last 20 prior coach messages for conversational context | Answer questions like "why is my weight not changing" | Same as above | Same as above |
| AI actions (propose) | The user's natural-language request only (e.g. "log a banana for breakfast") — no dashboard or history is sent | Turn the request into ONE structured, confirmable action proposal | Same as above | Same as above |
| Photo food recognition | The image bytes, inline as a `data:` URI, plus a fixed prompt. Nothing else — no user id, no email, no filename, and no hosted URL (a URL would mean storing the photo somewhere fetchable, which §8 forbids). Asserted by `test_the_image_is_sent_inline_and_nothing_else_is` | Identify likely foods so the user can pick a real one to log | Same as above | Same as above — **and food photos are a category worth checking specifically** before enabling this in production |

Never sent to any AI provider: email address, full name, password, authentication tokens, payment information — confirmed by what `coach_service.py`'s context builder actually queries (dashboard/weight/workout repositories only, never the user repository).

## Food photos (§8)

Photo recognition holds the image only for the length of the request:

- Read into memory from the upload, base64'd into the provider request, dropped when the request ends.
- Never written to disk, never put in object storage, never associated with any stored row. `test_a_recognized_photo_leaves_no_stored_record` asserts it.
- The response carries `image_retained: false` so a client can state this to the user rather than the user having to take it on trust.
- Type is sniffed from the bytes (JPEG/PNG/WebP); the declared Content-Type is attacker-controlled and ignored.
- Off unless an operator sets `AI_MODEL_VISION`. It is the only feature that sends a photograph anywhere, so it is opted into separately from the rest of AI rather than arriving with the API key.

Progress photos are a *different* feature with deliberately different handling: those are stored, in a private bucket, until the user deletes them. Don't conflate the two.

## Uncertainty & false precision

The coach's system prompt instructs it to state nutrition/calorie figures as approximate, never with false precision:

- Bad: "This meal contains exactly 647 calories."
- Good: "Estimated: approximately 600–700 calories."

For photo recognition this is enforced by construction rather than by prompt compliance:

- `RecognizedFoodItem` has **no scalar calorie field**. There is only `calories_min`/`calories_max`, so "exactly 647 calories" is not expressible no matter what the model returns.
- Any range narrower than 20% of its own midpoint is widened symmetrically before it reaches the user (`widen_narrow_range`). A model returning 646–648 kcal gets corrected rather than believed.
- Each item carries an explicit `confidence`, and the response carries `is_estimate: true`.
- The model's calorie estimate is *never* what gets logged. The user picks a real food from the database and confirms it; that food's deterministic nutrition is what reaches the diary.

Whether a given free-tier model actually complies with the coach's prompt is not independently verified without a live API key. The nutrition database, not the LLM, is the authoritative source for nutrition values in food parsing — the LLM only extracts item/quantity/unit, real calorie/macro values always come from `FoodNutrition` via the existing deterministic scaling in `nutrition_service.py`.

## No AI dependency for core data

Fitora's core loop (search food, log food, log workouts, view progress, track weight, view nutrition) works with the AI provider fully unavailable — confirmed by `get_ai_client()` returning `None` when `AI_API_KEY` is unset, which every AI route checks and turns into a 503 with a message pointing back to manual logging. No other endpoint depends on AI. Deterministic application logic (`calorie_service.py`) computes BMR/TDEE/calorie targets; the AI is never asked to do this math.

## Cost control

- Deterministic calculation for calories/macros (no LLM call) — `calorie_service.py`.
- Database search for known/custom foods before falling back to AI parsing — the app never calls AI automatically, only when the user explicitly uses natural-language logging.
- Per-IP rate limiting on both AI endpoints via `RATE_LIMIT_AI_PER_HOUR` (default 20/hour — keep at or below whatever the configured provider's free-tier ceiling actually is; OpenRouter free models have historically capped around 20 req/min and 200 req/day, but this changes, so verify before raising the limit).
- Default model (`nvidia/nemotron-3.5-lightning:free`) is free-tier; no per-request cost tracking is implemented since $0 doesn't need metering. If a paid model is configured later, add usage/cost tracking before relying on it in production.
- No response caching yet — each parse/coach call hits the provider. Revisit if free-tier rate limits become a practical problem.

## Health & safety guardrails

The coach's system prompt (`coach_service.py`) instructs it: never diagnose medical conditions; never recommend starting, stopping, or changing medication; never claim to cure disease; redirect medical or potentially urgent questions to a qualified healthcare professional or emergency services instead of answering directly; never encourage starvation, extreme calorie restriction, or dangerous exercise volume.

This is a prompt-level instruction, not a backend-enforced guarantee — there is no keyword filter or output classifier behind it. Compliance depends on the configured model actually following system instructions, which has not been verified against a live provider. Treat this as the first layer, not the only one, before any production launch.

### Extreme goals safety

Implemented deterministically in `calorie_service.py`/`goal_service.py`, not by the AI: if a requested goal target appears unsafe (below the minimum calorie floor, or too aggressive a rate of change), the API rejects it with the specific warnings unless the client explicitly acknowledges the risk. See `docs/database-schema.md` §Goals and the Phase 1 commit that added this. Gamification never rewards starvation, excessive restriction, dangerous exercise volume, or rapid weight loss.
