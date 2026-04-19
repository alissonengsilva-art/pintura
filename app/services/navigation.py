from app.services.access_control import SECTOR_OPTIONS, resolve_access_scope


PRIMARY_LINKS = [
    {"slug": "turnos", "title": "Turnos", "url": "/turno-atual"},
    {"slug": "dashboard", "title": "Dashboard", "url": "/dashboard"},
    {"slug": "relatorios", "title": "Relatorios", "url": "/relatorios"},
]

SECTIONS: list[dict] = []

CADASTRO_LINKS = [
    {"entity": "responsaveis", "title": "Responsveis", "url": "/cadastros/responsaveis"},
    {"entity": "modelos", "title": "Modelos", "url": "/cadastros/modelos"},
    {"entity": "setores", "title": "Setores", "url": "/cadastros/setores"},
    {"entity": "turnos", "title": "Turnos", "url": "/cadastros/turnos"},
    {"entity": "modulos-itens", "title": "Itens dos Módulos", "url": "/cadastros/modulos-itens"},
]


def layout_context(current_path: str, active_path: str | None = None, scope_source=None) -> dict:
    access_scope = resolve_access_scope(scope_source)
    return {
        "primary_links": PRIMARY_LINKS,
        "nav_sections": SECTIONS,
        "cadastro_links": CADASTRO_LINKS,
        "sector_scope_options": SECTOR_OPTIONS,
        "access_scope": access_scope,
        "current_path": current_path,
        "active_path": active_path or current_path,
    }
