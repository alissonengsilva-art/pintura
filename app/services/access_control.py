from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SECTOR_ALL = "TODOS"
SECTOR_PTED = "PTED"
SECTOR_LAB = "LABORATORIO"

SECTOR_OPTIONS = [
    {"value": SECTOR_ALL, "label": "Todos os setores"},
    {"value": SECTOR_PTED, "label": "PTED"},
    {"value": SECTOR_LAB, "label": "Laboratório"},
]

SECTOR_LABELS = {item["value"]: item["label"] for item in SECTOR_OPTIONS}


@dataclass(frozen=True)
class AccessScope:
    current_sector: str
    current_sector_label: str
    allowed_sectors: tuple[str, ...]
    enforcement_enabled: bool
    can_edit_pted: bool
    can_edit_laboratorio: bool
    restriction_mode_label: str


def resolve_access_scope(source: Any | None = None) -> AccessScope:
    selected_sector = SECTOR_ALL
    if source is not None and hasattr(source, "get"):
        selected_sector = str(source.get("setor_ativo") or SECTOR_ALL).strip().upper()

    if selected_sector not in {SECTOR_ALL, SECTOR_PTED, SECTOR_LAB}:
        selected_sector = SECTOR_ALL

    allowed = {
        SECTOR_ALL: (SECTOR_PTED, SECTOR_LAB),
        SECTOR_PTED: (SECTOR_PTED,),
        SECTOR_LAB: (SECTOR_LAB,),
    }[selected_sector]

    return AccessScope(
        current_sector=selected_sector,
        current_sector_label=SECTOR_LABELS[selected_sector],
        allowed_sectors=allowed,
        enforcement_enabled=False,
        can_edit_pted=SECTOR_PTED in allowed,
        can_edit_laboratorio=SECTOR_LAB in allowed,
        restriction_mode_label="Monitoramento livre" if selected_sector == SECTOR_ALL else "Escopo simulado",
    )
