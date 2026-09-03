# AI Safety & Architecture

**Implemented (Phase 3, this pass):** NL food parsing (`POST /ai/parse-food`) and a single-thread AI coach (`POST /ai/coach/messages`, `GET /ai/coach/messages`, `DELETE /ai/coach/messages`), both via [OpenRouter](https://openrouter.ai). See `app/services/ai/`.

**Not implemented:** tool-calling / mutating actions (`create_meal`, `log_food`, etc. below are the target design, not built yet — the coach is read-only/advisory and cannot write anything), photo food recognition, barcode-triggered AI. The coach explicitly tells the model it has no tools and cannot take actions; it can only discuss and suggest, and tells the user to log things themselves via the normal screens.

## Architecture (target — tool-calling not yet built)

```text
User → AI request → Backend → Validate request → Retrieve authorized user data
     → AI → Structured response → Backend validation → User confirmation (if mutating)
     → Database
```

The LLM never talks to the database, never receives raw credentials, and never executes arbitrary code or SQL. Today it:

1. Receives a system prompt plus **structured, minimum-necessary application data** the backend has already fetched and authorized for the requesting user (today's dashboard, recent weight, recent workout sessions for the coach; nothing beyond the raw text for parsing).
2. Returns plain text (coach) or a JSON array validated against a Pydantic schema (parsing) — never a tool call, since none exist yet.

## Tools (planned, not built)

```text
create_meal(user_id: from session, ...)
log_food(user_id: from session, ...)
create_workout(user_id: from session, ...)
update_weight(user_id: from session, ...)
```

When built, the rules for every tool will be:

- `user_id` is always taken from the authenticated session, never from AI output.
- Inputs are Pydantic-validated exactly like a normal API request.
- Business rules (e.g. sane weight ranges, sane macro ranges) are re-checked regardless of what the AI produced.
- Mutating tools that represent a meaningful change surface a confirmation step to the user before committing, unless the user has explicitly pre-authorized that class of action.

The AI must never be able to: access another user's data, execute arbitrary SQL, bypass application permissions, retrieve secrets, modify security settings, modify billing information, or access arbitrary files. This holds today by construction — there's nothing for the model to call.

## Prompt injection defense

User-provided text (food-parse input, coach messages, and anything embedded in the structured context like food/workout names) is **untrusted input**, always passed to the model as delimited data, never concatenated into system instructions.

Layers actually implemented:

- Fixed system prompts (`food_parser_service.py`, `coach_service.py`) that explicitly state user content is data, not instructions, and instruct the model to keep parsing/discussing even if the input looks like a command aimed at it.
- Structured JSON output requested for parsing, validated with Pydantic against `ParsedFoodItem`; free text is only accepted for the coach's conversational replies.
- Input length limits (`FoodParseRequest.text` ≤ 1000 chars, `CoachMessageCreateRequest.message` ≤ 2000 chars).
- Output validation after the model responds (schema for parsing; a non-empty, length-capped string for the coach) before anything is shown to the user or stored.
- No tool permissions exist yet, so there is nothing an injected instruction could invoke even if it succeeded.

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

Never sent to any AI provider: email address, full name, password, authentication tokens, payment information — confirmed by what `coach_service.py`'s context builder actually queries (dashboard/weight/workout repositories only, never the user repository).

## Uncertainty & false precision

The coach's system prompt instructs it to state nutrition/calorie figures as approximate, never with false precision:

- Bad: "This meal contains exactly 647 calories."
- Good: "Estimated: approximately 600–700 calories."

Whether a given free-tier model actually complies is not independently verified without a live API key. The nutrition database, not the LLM, is the authoritative source for nutrition values in food parsing — the LLM only extracts item/quantity/unit, real calorie/macro values always come from `FoodNutrition` via the existing deterministic scaling in `nutrition_service.py`.

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
