import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.policy import POLICY_VERSION
from app.models.activity_entry import ActivityEntry
from app.models.ai_message import AIMessageRecord
from app.models.audit import AuditEventType
from app.models.body_measurement import BodyMeasurement
from app.models.goal import Goal
from app.models.nutrition import Food, FoodDiaryEntry, FoodNutrition, FoodSource
from app.models.profile import UserProfile
from app.models.progress_photo import ProgressPhoto
from app.models.user import User, UserSession, UserStatus
from app.models.water_entry import WaterEntry
from app.models.weight_entry import WeightEntry
from app.models.workout import Workout, WorkoutExercise, WorkoutSession, WorkoutSet
from app.services.audit_service import AuditService
from app.services.consent_service import ConsentService
from app.services.storage.base import ObjectStorage, StorageError

logger = logging.getLogger("fitora")

EXPORT_FORMAT_VERSION = "1"


def _iso(value: Any) -> Any:
    """Coerce ORM values into JSON-serializable ones.

    Numeric columns come back as `Decimal`, which `json.dumps` refuses. They
    are converted to float here rather than to string so the export stays
    usable as data -- these are quantities a reader will want to compute with,
    and none of them need more precision than a float carries.
    """
    if isinstance(value, datetime | UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _row(obj: object, fields: tuple[str, ...]) -> dict[str, Any]:
    return {name: _iso(getattr(obj, name)) for name in fields}


class AccountService:
    """Data-rights operations: export everything, delete everything (§29).

    Deletion is deliberately explicit rather than leaning on database cascade.
    Two reasons: `food_diary_entries.food_id` is ON DELETE RESTRICT while both
    that table and `foods` cascade from `users`, so cascade ordering could
    block the delete; and SQLite (used by the test suite) does not enforce
    foreign keys by default, so a cascade-based implementation would be
    untestable there and would only fail in production.
    """

    def __init__(self, db: AsyncSession, storage: ObjectStorage | None = None) -> None:
        self.db = db
        self.storage = storage
        self.audit = AuditService(db)
        self.consent = ConsentService(db)

    # --- export -----------------------------------------------------------

    async def export(self, user: User) -> dict[str, Any]:
        """Everything Fitora holds about this user, as machine-readable JSON.

        Excludes the password hash and refresh-token hashes -- those are
        credentials, not personal data, and exporting them would only create a
        new place for them to leak. Progress photos are listed as metadata;
        the image bytes are fetched separately through the photos API, since
        embedding them would make the export unusably large.
        """
        uid = user.id

        async def all_of(model: Any, order: Any, fields: tuple[str, ...]) -> list[dict[str, Any]]:
            result = await self.db.execute(
                select(model).where(model.user_id == uid).order_by(order)
            )
            return [_row(row, fields) for row in result.scalars().all()]

        diary_result = await self.db.execute(
            select(FoodDiaryEntry, Food)
            .join(Food, Food.id == FoodDiaryEntry.food_id)
            .where(FoodDiaryEntry.user_id == uid)
            .order_by(FoodDiaryEntry.logged_at, FoodDiaryEntry.created_at)
        )
        food_diary = [
            {
                **_row(
                    entry,
                    (
                        "id",
                        "logged_at",
                        "meal_category",
                        "quantity",
                        "unit",
                        "source",
                        "created_at",
                    ),
                ),
                "food_name": food.name,
                "food_brand": food.brand,
                "serving_description": food.serving_description,
            }
            for entry, food in diary_result.all()
        ]

        custom_foods_result = await self.db.execute(
            select(Food, FoodNutrition)
            .join(FoodNutrition, FoodNutrition.food_id == Food.id)
            .where(Food.owner_user_id == uid, Food.source == FoodSource.USER)
            .order_by(Food.name)
        )
        custom_foods = [
            {
                **_row(food, ("id", "name", "brand", "serving_description", "serving_grams")),
                **_row(
                    nutrition,
                    ("per_grams", "calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"),
                ),
            }
            for food, nutrition in custom_foods_result.all()
        ]

        workouts_result = await self.db.execute(
            select(Workout).where(Workout.user_id == uid).order_by(Workout.created_at)
        )
        workouts: list[dict[str, Any]] = []
        for workout in workouts_result.scalars().all():
            exercises = await self.db.execute(
                select(WorkoutExercise)
                .where(WorkoutExercise.workout_id == workout.id)
                .order_by(WorkoutExercise.order_index)
            )
            workouts.append(
                {
                    **_row(workout, ("id", "name", "workout_type", "created_at")),
                    "exercises": [
                        _row(
                            we,
                            (
                                "id",
                                "exercise_id",
                                "order_index",
                                "target_sets",
                                "target_reps",
                                "target_weight_kg",
                            ),
                        )
                        for we in exercises.scalars().all()
                    ],
                }
            )

        sessions_result = await self.db.execute(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == uid)
            .order_by(WorkoutSession.started_at)
        )
        workout_sessions: list[dict[str, Any]] = []
        for session in sessions_result.scalars().all():
            sets = await self.db.execute(
                select(WorkoutSet)
                .where(WorkoutSet.workout_session_id == session.id)
                .order_by(WorkoutSet.set_number)
            )
            workout_sessions.append(
                {
                    **_row(session, ("id", "workout_id", "started_at", "ended_at", "notes")),
                    "sets": [
                        _row(
                            s,
                            (
                                "id",
                                "exercise_id",
                                "set_number",
                                "reps",
                                "weight_kg",
                                "duration_seconds",
                                "distance_m",
                                "rest_seconds",
                                "notes",
                            ),
                        )
                        for s in sets.scalars().all()
                    ],
                }
            )

        profile_result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == uid)
        )
        profile = profile_result.scalar_one_or_none()

        return {
            "export_format_version": EXPORT_FORMAT_VERSION,
            "exported_at": datetime.now(UTC).isoformat(),
            "policy_version": POLICY_VERSION,
            "notes": (
                "Credentials (password hash, refresh tokens) are deliberately excluded. "
                "Progress photos are listed as metadata only — download the images "
                "themselves from the progress-photos API before deleting your account."
            ),
            "account": _row(user, ("id", "email", "status", "email_verified_at", "created_at")),
            "profile": (
                _row(
                    profile,
                    (
                        "display_name",
                        "date_of_birth",
                        "sex",
                        "height_cm",
                        "activity_level",
                        "unit_system",
                    ),
                )
                if profile is not None
                else None
            ),
            "goals": await all_of(
                Goal,
                Goal.created_at,
                (
                    "id",
                    "goal_type",
                    "intensity",
                    "target_weight_kg",
                    "target_calories",
                    "target_protein_g",
                    "target_carbs_g",
                    "target_fat_g",
                    "target_water_ml",
                    "ends_at",
                    "is_active",
                    "created_at",
                ),
            ),
            "food_diary": food_diary,
            "custom_foods": custom_foods,
            "water_entries": await all_of(
                WaterEntry, WaterEntry.logged_at, ("id", "logged_at", "amount_ml")
            ),
            "weight_entries": await all_of(
                WeightEntry, WeightEntry.logged_at, ("id", "logged_at", "weight_kg")
            ),
            "body_measurements": await all_of(
                BodyMeasurement,
                BodyMeasurement.logged_at,
                ("id", "logged_at", "waist_cm", "chest_cm", "arm_cm", "leg_cm", "hip_cm"),
            ),
            "activity_entries": await all_of(
                ActivityEntry,
                ActivityEntry.logged_at,
                (
                    "id",
                    "logged_at",
                    "activity_type",
                    "duration_min",
                    "distance_km",
                    "steps",
                    "calories_burned",
                    "source",
                    "notes",
                ),
            ),
            "workouts": workouts,
            "workout_sessions": workout_sessions,
            "progress_photos": await all_of(
                ProgressPhoto,
                ProgressPhoto.taken_at,
                ("id", "taken_at", "content_type", "size_bytes", "created_at"),
            ),
            "ai_messages": await all_of(
                AIMessageRecord, AIMessageRecord.created_at, ("id", "role", "content", "created_at")
            ),
            "consent_records": [
                _row(r, ("id", "consent_type", "granted", "policy_version", "recorded_at"))
                for r in await self.consent.history(uid)
            ],
            "audit_events": [
                {
                    **_row(e, ("id", "event_type", "created_at")),
                    "metadata": e.event_metadata,
                }
                for e in await self.audit.list_for_user(uid)
            ],
        }

    # --- deletion ---------------------------------------------------------

    async def delete_account(self, user: User) -> None:
        """Irreversibly delete the account and everything owned by it.

        Follows `docs/data-flow.md` §"Account deletion flow": the account is
        marked `pending_deletion` first so a failure part-way through cannot
        leave a usable login behind, stored objects go before their rows, and
        audit/consent records are anonymized rather than deleted.
        """
        uid = user.id

        # 1. Block login immediately, before any slow object-storage work.
        user.status = UserStatus.PENDING_DELETION
        await self.db.flush()

        # 2. Stored objects first: a deleted row whose object survives is a
        #    private image nobody can find to remove.
        await self._delete_stored_photos(uid)

        # 3. Rows, in dependency order (see the class docstring for why this
        #    is explicit rather than relying on cascade).
        await self.db.execute(delete(AIMessageRecord).where(AIMessageRecord.user_id == uid))
        await self.db.execute(delete(FoodDiaryEntry).where(FoodDiaryEntry.user_id == uid))

        owned_food_ids = select(Food.id).where(Food.owner_user_id == uid)
        await self.db.execute(
            delete(FoodNutrition).where(FoodNutrition.food_id.in_(owned_food_ids))
        )
        await self.db.execute(delete(Food).where(Food.owner_user_id == uid))

        session_ids = select(WorkoutSession.id).where(WorkoutSession.user_id == uid)
        await self.db.execute(
            delete(WorkoutSet).where(WorkoutSet.workout_session_id.in_(session_ids))
        )
        await self.db.execute(delete(WorkoutSession).where(WorkoutSession.user_id == uid))

        workout_ids = select(Workout.id).where(Workout.user_id == uid)
        await self.db.execute(
            delete(WorkoutExercise).where(WorkoutExercise.workout_id.in_(workout_ids))
        )
        await self.db.execute(delete(Workout).where(Workout.user_id == uid))

        deletable_by_user: tuple[Any, ...] = (
            WaterEntry,
            WeightEntry,
            BodyMeasurement,
            ActivityEntry,
            ProgressPhoto,
            Goal,
            UserProfile,
            UserSession,
        )
        for model in deletable_by_user:
            await self.db.execute(delete(model).where(model.user_id == uid))

        # 4. Anonymize rather than delete: these have to outlive the account
        #    while ceasing to identify anyone.
        await self.audit.anonymize_user(uid)
        await self.consent.anonymize_user(uid)

        # 5. A final event with no user_id, so the deletion itself is on the
        #    record without re-identifying the person it describes.
        await self.audit.record(
            event_type=AuditEventType.ACCOUNT_DELETED,
            user_id=None,
            metadata={"policy_version": POLICY_VERSION},
        )

        await self.db.execute(delete(User).where(User.id == uid))
        await self.db.commit()

    async def _delete_stored_photos(self, user_id: UUID) -> None:
        result = await self.db.execute(
            select(ProgressPhoto.storage_key).where(ProgressPhoto.user_id == user_id)
        )
        keys = list(result.scalars().all())
        if not keys:
            return

        if self.storage is None:
            # Deleting the account is the user's right and must not be blocked
            # by an ops misconfiguration, but orphaned private images are a
            # real problem, so make them findable in the logs.
            logger.error(
                "account deletion left %d progress-photo object(s) in storage: "
                "object storage is not configured on this server, so they could "
                "not be removed. Keys: %s",
                len(keys),
                ", ".join(keys),
            )
            return

        for key in keys:
            try:
                await self.storage.delete(key=key)
            except StorageError:
                # Same trade-off: log loudly, keep deleting.
                logger.exception(
                    "account deletion could not remove progress-photo object %s", key
                )


__all__ = ["EXPORT_FORMAT_VERSION", "AccountService"]
