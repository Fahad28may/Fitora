from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_message import AIMessageRecord, MessageRole

MAX_HISTORY_MESSAGES = 20


class AIMessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, user_id: UUID, role: MessageRole, content: str) -> AIMessageRecord:
        message = AIMessageRecord(user_id=user_id, role=role, content=content)
        self.db.add(message)
        await self.db.flush()
        return message

    async def list_recent(
        self, user_id: UUID, limit: int = MAX_HISTORY_MESSAGES
    ) -> list[AIMessageRecord]:
        result = await self.db.execute(
            select(AIMessageRecord)
            .where(AIMessageRecord.user_id == user_id)
            .order_by(AIMessageRecord.created_at.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def clear(self, user_id: UUID) -> None:
        await self.db.execute(delete(AIMessageRecord).where(AIMessageRecord.user_id == user_id))
        await self.db.flush()
