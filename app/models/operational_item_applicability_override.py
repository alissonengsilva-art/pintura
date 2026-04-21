from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin


OVERRIDE_STATUS_AUTOMATIC = "automatic"
OVERRIDE_STATUS_APPLICABLE = "applicable"
OVERRIDE_STATUS_NOT_APPLICABLE = "not_applicable"
OVERRIDE_STATUS_DISPENSED = "dispensed"


class OperationalItemApplicabilityOverride(Base, TimestampMixin):
    __tablename__ = "operational_item_applicability_overrides"
    __table_args__ = (
        UniqueConstraint("shift_id", "operational_module_item_id", name="uq_shift_item_applicability_override"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_id: Mapped[int] = mapped_column(
        ForeignKey("operational_shifts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operational_module_item_id: Mapped[int] = mapped_column(
        ForeignKey("operational_module_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    override_status: Mapped[str] = mapped_column(String(20), nullable=False, default=OVERRIDE_STATUS_AUTOMATIC)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
