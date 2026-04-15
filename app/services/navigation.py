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
    },
    {
        "slug": "temperatura-forno-ed",
        "title": "Temperatura Forno ED",
        "description": "Módulo operacional para leitura térmica das 12 zonas do forno com destaque de desvios.",
        "url": "/temperatura-forno-ed",
        "status": "operacional",
    },
    {
        "slug": "pressao-filtros-ed",
        "title": "Pressão dos filtros ED",
        "description": "Módulo operacional para leitura dos 24 filtros com identificação de alarmes.",
        "url": "/pressao-filtros-ed",
        "status": "operacional",
    },
    {
        "slug": "tensao-retificadores-ed",
        "title": "Tensão dos retificadores ED",
        "description": "Módulo operacional para leituras por turno e modelo nas 29 zonas dos retificadores.",
        "url": "/tensao-retificadores-ed",
        "status": "operacional",
    },
    {
        "slug": "poder-penetracao",
        "title": "Poder de penetração",
        "description": "Módulo operacional semanal com 30 pontos e cálculo automático de % de aprovação.",
        "url": "/poder-penetracao",
        "status": "operacional",
    },
    {
        "slug": "espessura-ed",
        "title": "Espessura ED",
        "description": "Módulo operacional para medições técnicas de espessura em 38 pontos por turno e modelo.",
        "url": "/espessura-ed",
        "status": "operacional",
    },
    {
        "slug": "aspecto",
        "title": "Aspecto",
        "description": "Módulo operacional para registrar anomalias visuais por carroceria em lotes rápidos por turno.",
        "url": "/aspecto",
        "status": "operacional",
    },
    {
        "slug": "rugosidade",
        "title": "Rugosidade",
        "description": "Módulo operacional matricial por data e sequência com controle técnico dos 5 modelos fixos.",
        "url": "/rugosidade",
        "status": "operacional",
    },
]

CADASTRO_LINKS = [
    {"entity": "responsaveis", "title": "Responsáveis", "url": "/cadastros/responsaveis"},
    {"entity": "modelos", "title": "Modelos", "url": "/cadastros/modelos"},
    {"entity": "setores", "title": "Setores", "url": "/cadastros/setores"},
    {"entity": "turnos", "title": "Turnos", "url": "/cadastros/turnos"},
    {"entity": "itens-ed", "title": "Itens ED", "url": "/cadastros/itens-ed"},
]


def layout_context(current_path: str, active_path: str | None = None) -> dict:
    return {
        "primary_links": PRIMARY_LINKS,
        "nav_sections": SECTIONS,
        "cadastro_links": CADASTRO_LINKS,
        "current_path": current_path,
        "active_path": active_path or current_path,
    }
