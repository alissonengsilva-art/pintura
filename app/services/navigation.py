from app.services.access_control import SECTOR_LAB, SECTOR_PTED, SECTOR_OPTIONS, resolve_access_scope


PRIMARY_LINKS = [
    {"slug": "dashboard", "title": "Dashboard", "url": "/dashboard"},
    {"slug": "pendencias", "title": "Pendências", "url": "/pendencias"},
]


SECTIONS = [
    {
        "slug": "ed",
        "title": "ED",
        "description": "Checklist principal e porta de entrada operacional.",
        "url": "/ed",
        "status": "operacional",
        "setores": (SECTOR_PTED, SECTOR_LAB),
        "future_access_ready": True,
    },
    {
        "slug": "temperatura-forno-ed",
        "title": "Temperatura Forno",
        "description": "Módulo operacional para leitura térmica das 12 zonas do forno com destaque de desvios.",
        "url": "/temperatura-forno-ed",
        "status": "operacional",
        "setores": (SECTOR_PTED, SECTOR_LAB),
        "future_access_ready": True,
    },
    {
        "slug": "pressao-filtros-ed",
        "title": "Pressão dos filtros",
        "description": "Módulo operacional para leitura dos 24 filtros com identificação de alarmes.",
        "url": "/pressao-filtros-ed",
        "status": "operacional",
        "setores": (SECTOR_PTED, SECTOR_LAB),
        "future_access_ready": True,
    },
    {
        "slug": "tensao-retificadores-ed",
        "title": "Tensão dos retificadores",
        "description": "Módulo operacional para leituras por turno e modelo nas 29 zonas dos retificadores.",
        "url": "/tensao-retificadores-ed",
        "status": "operacional",
        "setores": (SECTOR_PTED, SECTOR_LAB),
        "future_access_ready": True,
    },
    {
        "slug": "poder-penetracao",
        "title": "Poder de penetração",
        "description": "Módulo operacional semanal com 30 pontos e cálculo automático de % de aprovação.",
        "url": "/poder-penetracao",
        "status": "operacional",
        "setores": (SECTOR_PTED, SECTOR_LAB),
        "future_access_ready": True,
    },
    {
        "slug": "espessura-ed",
        "title": "Espessura",
        "description": "Módulo operacional para medições técnicas de espessura em 38 pontos por turno e modelo.",
        "url": "/espessura-ed",
        "status": "operacional",
        "setores": (SECTOR_PTED, SECTOR_LAB),
        "future_access_ready": True,
    },
    {
        "slug": "aspecto",
        "title": "Aspecto",
        "description": "Módulo operacional para registrar anomalias visuais por carroceria em lotes rápidos por turno.",
        "url": "/aspecto",
        "status": "operacional",
        "setores": (SECTOR_PTED, SECTOR_LAB),
        "future_access_ready": True,
    },
    {
        "slug": "rugosidade",
        "title": "Rugosidade",
        "description": "Módulo operacional matricial por data e sequência com controle técnico dos 5 modelos fixos.",
        "url": "/rugosidade",
        "status": "operacional",
        "setores": (SECTOR_PTED, SECTOR_LAB),
        "future_access_ready": True,
    },
]

CADASTRO_LINKS = [
    {"entity": "responsaveis", "title": "Responsáveis", "url": "/cadastros/responsaveis"},
    {"entity": "modelos", "title": "Modelos", "url": "/cadastros/modelos"},
    {"entity": "setores", "title": "Setores", "url": "/cadastros/setores"},
    {"entity": "turnos", "title": "Turnos", "url": "/cadastros/turnos"},
    {"entity": "itens-ed", "title": "Itens ED", "url": "/cadastros/itens-ed"},
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
