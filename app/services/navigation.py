from app.services.access_control import SECTOR_OPTIONS, resolve_access_scope


PRIMARY_LINKS = [
    {"slug": "dashboard", "title": "Dashboard", "url": "/dashboard", "active_paths": ["/dashboard"]},
    {
        "slug": "operacoes",
        "title": "Operações",
        "url": "/operacoes",
        "active_paths": [
            "/operacoes",
            "/turnos-pt",
            "/turnos-ed",
            "/turno-atual",
            "/turnos",
            "/turnos-sigilatura",
            "/central-tintas",
            "/central-de-tintas",
            "/cabine-pintura",
        ],
    },
    {"slug": "relatorios", "title": "Relatorios", "url": "/relatorios", "active_paths": ["/relatorios"]},
]

SECTIONS: list[dict] = [
    {"slug": "visao-geral", "title": "Visão Geral", "links": [PRIMARY_LINKS[0]]},
    {"slug": "operacao", "title": "Operação", "links": [PRIMARY_LINKS[1]]},
    {"slug": "relatorios", "title": "Relatórios", "links": [PRIMARY_LINKS[2]]},
]

ADMIN_LINKS = [
    {"slug": "configuracoes", "title": "Configurações", "url": "/configuracoes"},
]

SETTINGS_HUB_ITEMS = [
    {
        "slug": "responsaveis",
        "title": "Responsáveis",
        "description": "Cadastre e mantenha os colaboradores vinculados aos setores operacionais.",
        "url": "/cadastros/responsaveis",
    },
    {
        "slug": "modelos",
        "title": "Modelos",
        "description": "Gerencie os modelos usados nos lançamentos e nas consultas operacionais.",
        "url": "/cadastros/modelos",
    },
    {
        "slug": "setores",
        "title": "Setores",
        "description": "Ajuste os setores disponíveis para cadastros, filtros e contexto operacional.",
        "url": "/cadastros/setores",
    },
    {
        "slug": "turnos",
        "title": "Turnos",
        "description": "Mantenha a estrutura de turnos utilizada pelo painel e pelos filtros.",
        "url": "/cadastros/turnos",
    },
    {
        "slug": "modulos-itens",
        "title": "Controles",
        "description": "Cadastre, edite e organize os itens e sua periodicidade operacional.",
        "url": "/configuracoes/modulos-itens",
    },
]


def _normalize_path(path: str | None) -> str:
    value = str(path or "").strip() or "/"
    if value != "/" and value.endswith("/"):
        value = value.rstrip("/")
    return value


def _is_active_link(current_path: str, active_path: str, item: dict) -> bool:
    normalized_current = _normalize_path(current_path)
    normalized_active = _normalize_path(active_path)
    for raw_target in item.get("active_paths") or [item["url"]]:
        target = _normalize_path(raw_target)
        if normalized_current == target or normalized_active == target:
            return True
        if target != "/" and (
            normalized_current.startswith(f"{target}/") or normalized_active.startswith(f"{target}/")
        ):
            return True
    return False


def _build_sections(current_path: str, active_path: str) -> list[dict]:
    sections: list[dict] = []
    for section in SECTIONS:
        links = []
        for item in section["links"]:
            enriched_item = dict(item)
            enriched_item["is_active"] = _is_active_link(current_path, active_path, item)
            links.append(enriched_item)
        sections.append({**section, "links": links})
    return sections


def layout_context(current_path: str, active_path: str | None = None, scope_source=None) -> dict:
    access_scope = resolve_access_scope(scope_source)
    resolved_active_path = active_path or current_path
    active_page = "dashboard"
    if resolved_active_path.startswith("/operacoes") or resolved_active_path.startswith("/turnos"):
        active_page = "operacoes"
    elif resolved_active_path.startswith("/relatorios"):
        active_page = "relatorios"
    elif resolved_active_path.startswith("/configuracoes"):
        active_page = "configuracoes"
    return {
        "primary_links": PRIMARY_LINKS,
        "nav_sections": _build_sections(current_path, resolved_active_path),
        "admin_links": ADMIN_LINKS,
        "settings_hub_items": SETTINGS_HUB_ITEMS,
        "sector_scope_options": SECTOR_OPTIONS,
        "access_scope": access_scope,
        "current_path": current_path,
        "active_path": resolved_active_path,
        "active_page": active_page,
    }
