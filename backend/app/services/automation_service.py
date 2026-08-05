from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.sequence import Sequence, SequenceStep
from app.schemas.automation import SequenceCreate


async def list_sequences(session: AsyncSession, workspace_id: str) -> list[Sequence]:
    query = (
        select(Sequence)
        .where(Sequence.workspace_id == workspace_id)
        .options(selectinload(Sequence.steps))
        .order_by(Sequence.created_at.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().unique().all())


async def get_sequence(session: AsyncSession, workspace_id: str, sequence_id: str) -> Optional[Sequence]:
    query = (
        select(Sequence)
        .where(Sequence.id == sequence_id, Sequence.workspace_id == workspace_id)
        .options(selectinload(Sequence.steps))
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def create_sequence(session: AsyncSession, workspace_id: str, data: SequenceCreate) -> Sequence:
    sequence = Sequence(workspace_id=workspace_id, name=data.name, trigger=data.trigger, status="draft")
    session.add(sequence)
    await session.flush()

    for i, step in enumerate(data.steps):
        session.add(
            SequenceStep(
                sequence_id=sequence.id,
                step_order=i,
                delay_hours=step.delay_hours,
                subject=step.subject,
                body=step.body
            )
        )

    await session.commit()
    return await get_sequence(session, workspace_id, sequence.id)  # type: ignore[return-value]


async def update_status(session: AsyncSession, sequence: Sequence, status_label: str) -> Sequence:
    sequence.status = status_label
    await session.commit()
    await session.refresh(sequence, attribute_names=["steps"])
    return sequence


async def delete_sequence(session: AsyncSession, sequence: Sequence) -> None:
    await session.delete(sequence)
    await session.commit()
