from app.services.access_control import SECTOR_OPTIONS, resolve_access_scope


PRIMARY_LINKS = [
    {"slug": "dashboard", "title": "Dashboard", "url": "/dashboard"},
    {"slug": "turnos", "title": "ED", "url": "/turno-atual"},
    {"slug": "turnos-sigilatura", "title": "Sigilatura", "url": "/turnos-sigilatura"},
    {"slug": "central-tintas", "title": "Central de Tintas", "url": "/central-tintas"},
    {"slug": "relatorios", "title": "Relatórios", "url": "/relatorios"},
]

SECTIONS: list[dict] = []

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
    {
        "slug": "temperatura-faixas",
        "title": "Edição Geral de Parâmetros",
        "description": "Edite parâmetros e referências dos módulos de ED e Sigilatura em uma única tela.",
        "url": "/cadastros/modulos-itens/temperatura-forno-ed/faixas",
    },
]


def layout_context(current_path: str, active_path: str | None = None, scope_source=None) -> dict:
    access_scope = resolve_access_scope(scope_source)
    return {
        "primary_links": PRIMARY_LINKS,
        "nav_sections": SECTIONS,
        "admin_links": ADMIN_LINKS,
        "settings_hub_items": SETTINGS_HUB_ITEMS,
        "sector_scope_options": SECTOR_OPTIONS,
        "access_scope": access_scope,
        "current_path": current_path,
        "active_path": active_path or current_path,
    }


