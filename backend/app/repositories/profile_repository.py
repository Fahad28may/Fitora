from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import Goal
from app.models.profile import UserProfile


class ProfileRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, user_id: UUID) -> UserProfile | None:
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, user_id: UUID, **fields: object) -> UserProfile:
        profile = await self.get(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id, **fields)
            self.db.add(profile)
        else:
            for key, value in fields.items():
                setattr(profile, key, value)
        await self.db.flush()
        return profile


class GoalRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_active(self, user_id: UUID) -> Goal | None:
        result = await self.db.execute(
            select(Goal).where(Goal.user_id == user_id, Goal.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, goal_id: UUID) -> Goal | None:
        result = await self.db.execute(select(Goal).where(Goal.id == goal_id))
        return result.scalar_one_or_none()

    async def create(self, **fields: object) -> Goal:
        goal = Goal(**fields)
        self.db.add(goal)
        await self.db.flush()
        return goal

    async def deactivate_all(self, user_id: UUID) -> None:
        active = await self.get_active(user_id)
        if active is not None:
            active.is_active = False
            await self.db.flush()
