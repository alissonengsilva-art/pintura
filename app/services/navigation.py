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
        "description": "Área reservada para futuros formulários e rastreabilidade.",
        "url": "/poder-penetracao",
        "status": "em breve",
    },
    {
        "slug": "espessura-ed",
        "title": "Espessura ED",
        "description": "Base visual para controle de espessura do filme.",
        "url": "/espessura-ed",
        "status": "em breve",
    },
    {
        "slug": "aspecto",
        "title": "Aspecto",
        "description": "Página preparada para avaliações visuais e critérios futuros.",
        "url": "/aspecto",
        "status": "em breve",
    },
    {
        "slug": "rugosidade",
        "title": "Rugosidade",
        "description": "Seção inicial para evolução do acompanhamento superficial.",
        "url": "/rugosidade",
        "status": "em breve",
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
        "nav_sections": SECTIONS,
        "cadastro_links": CADASTRO_LINKS,
        "current_path": current_path,
        "active_path": active_path or current_path,
    }
