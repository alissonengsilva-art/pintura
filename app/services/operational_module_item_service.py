from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import OperationalModuleItem


SECTOR_BOTH = "AMBOS"


def get_items_ordered(session: Session, module_code: str) -> list[OperationalModuleItem]:
    return list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == module_code)
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )


def get_active_items(session: Session, module_code: str) -> list[OperationalModuleItem]:
    return list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == module_code)
            .where(OperationalModuleItem.ativo.is_(True))
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )


def get_items_by_module(session: Session, module_code: str) -> list[OperationalModuleItem]:
    return get_active_items(session, module_code)


def get_items_by_module_and_setor(session: Session, module_code: str, setor: str) -> list[OperationalModuleItem]:
    return list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == module_code)
            .where(OperationalModuleItem.ativo.is_(True))
            .where(or_(OperationalModuleItem.setor_tipo == setor, OperationalModuleItem.setor_tipo == SECTOR_BOTH))
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )


def get_item_map_by_legacy_ed_id(session: Session) -> dict[int, OperationalModuleItem]:
    items = list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "ed")
            .where(OperationalModuleItem.legacy_item_ed_id.is_not(None))
        ).all()
    )
    return {int(item.legacy_item_ed_id): item for item in items if item.legacy_item_ed_id is not None}
