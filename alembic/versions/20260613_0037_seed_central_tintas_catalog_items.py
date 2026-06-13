"""seed central tintas catalog items

Revision ID: 20260613_0037
Revises: 20260613_0036
Create Date: 2026-06-13 09:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260613_0037"
down_revision = "20260613_0036"
branch_labels = None
depends_on = None


CATALOG_ITEMS = [
    ("VERNIZ 1 PPG", "TEMPERATURA", "<23°C"),
    ("VERNIZ 1 PPG", "VISCOSIDADE", "35 - 37"),
    ("VERNIZ 1 PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("VERNIZ 2 AXALTA", "TEMPERATURA", "<25°C"),
    ("VERNIZ 2 AXALTA", "VISCOSIDADE", "29 - 31"),
    ("VERNIZ 2 AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("B1 UNIVERSAL PPG", "TEMPERATURA", "20 - 28°C"),
    ("B1 UNIVERSAL PPG", "VISCOSIDADE", "80 - 100"),
    ("B1 UNIVERSAL PPG", "pH", "8,4 - 8,8"),
    ("B1 UNIVERSAL PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("B0 MEDIUM AXALTA", "TEMPERATURA", "22 - 28°C"),
    ("B0 MEDIUM AXALTA", "VISCOSIDADE", "110 - 140"),
    ("B0 MEDIUM AXALTA", "pH", "8,4 - 8,8"),
    ("B0 MEDIUM AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("BRANCO AMBIENTE AXALTA", "TEMPERATURA", "20 - 28°C"),
    ("BRANCO AMBIENTE AXALTA", "VISCOSIDADE", "110 - 190"),
    ("BRANCO AMBIENTE AXALTA", "pH", "8,0 - 9,0"),
    ("BRANCO AMBIENTE AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("PRETO SHADOW AXALTA", "TEMPERATURA", "20 - 28°C"),
    ("PRETO SHADOW AXALTA", "VISCOSIDADE", "110 - 140"),
    ("PRETO SHADOW AXALTA", "pH", "8,2 - 8,6"),
    ("PRETO SHADOW AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("PRETO SHADOW PPG", "TEMPERATURA", "20 - 28°C"),
    ("PRETO SHADOW PPG", "VISCOSIDADE", "85 - 95"),
    ("PRETO SHADOW PPG", "pH", "8,4 - 9,2"),
    ("PRETO SHADOW PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("VERMELHO COLORADO PPG", "TEMPERATURA", "20 - 28°C"),
    ("VERMELHO COLORADO PPG", "VISCOSIDADE", "85 - 95"),
    ("VERMELHO COLORADO PPG", "pH", "8,4 - 8,8"),
    ("VERMELHO COLORADO PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("PRETO CARBON PPG", "TEMPERATURA", "20 - 28°C"),
    ("PRETO CARBON PPG", "VISCOSIDADE", "60 - 80"),
    ("PRETO CARBON PPG", "pH", "8,4 - 8,8"),
    ("PRETO CARBON PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("BRANCO POLAR AXALTA", "TEMPERATURA", "20 - 28°C"),
    ("BRANCO POLAR AXALTA", "VISCOSIDADE", "80 - 90"),
    ("BRANCO POLAR AXALTA", "pH", "8,4 - 8,8"),
    ("BRANCO POLAR AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("BILLET SILVER PPG", "TEMPERATURA", "20 - 28°C"),
    ("BILLET SILVER PPG", "VISCOSIDADE", "80 - 100"),
    ("BILLET SILVER PPG", "pH", "8,4 - 8,9"),
    ("BILLET SILVER PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("JAZZ BLUE PPG", "TEMPERATURA", "20 - 28°C"),
    ("JAZZ BLUE PPG", "VISCOSIDADE", "80 - 100"),
    ("JAZZ BLUE PPG", "pH", "8,4 - 8,8"),
    ("JAZZ BLUE PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("GRANITE CRYSTAL PPG", "TEMPERATURA", "20 - 28°C"),
    ("GRANITE CRYSTAL PPG", "VISCOSIDADE", "80 - 100"),
    ("GRANITE CRYSTAL PPG", "pH", "8,4 - 8,8"),
    ("GRANITE CRYSTAL PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("STING GRAY AXALTA", "TEMPERATURA", "20 - 28°C"),
    ("STING GRAY AXALTA", "VISCOSIDADE", "80 - 100"),
    ("STING GRAY AXALTA", "pH", "8,4 - 8,8"),
    ("STING GRAY AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("SLASH GOLD PPG", "TEMPERATURA", "20 - 28°C"),
    ("SLASH GOLD PPG", "VISCOSIDADE", "80 - 100"),
    ("SLASH GOLD PPG", "pH", "8,4 - 8,8"),
    ("SLASH GOLD PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("MAXIMUM STEEL PPG", "TEMPERATURA", "20 - 28°C"),
    ("MAXIMUM STEEL PPG", "VISCOSIDADE", "80 - 100"),
    ("MAXIMUM STEEL PPG", "pH", "8,4 - 8,8"),
    ("MAXIMUM STEEL PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("PUNK ORANGE AXALTA", "TEMPERATURA", "20 - 28°C"),
    ("PUNK ORANGE AXALTA", "VISCOSIDADE", "80 - 100"),
    ("PUNK ORANGE AXALTA", "pH", "8,4 - 8,9"),
    ("PUNK ORANGE AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("VERDE RECON PPG", "TEMPERATURA", "20 - 28°C"),
    ("VERDE RECON PPG", "VISCOSIDADE", "75 - 85"),
    ("VERDE RECON PPG", "pH", "8,4 - 8,8"),
    ("VERDE RECON PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ("MONOCOAT PPG", "TEMPERATURA", "<23°C"),
    ("MONOCOAT PPG", "VISCOSIDADE", "27 - 32"),
    ("MONOCOAT PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
]


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    op_items = sa.Table("operational_module_items", metadata, autoload_with=bind)

    existing_rows = list(
        bind.execute(
            sa.select(
                op_items.c.id,
                op_items.c.operacao,
                op_items.c.controle,
                op_items.c.parametro,
                op_items.c.parametro_exibicao,
            ).where(op_items.c.module_code == "central-tintas")
        ).mappings()
    )
    existing_map = {
        (
            str(row["operacao"] or "").strip().lower(),
            str(row["controle"] or "").strip().lower(),
            str(row["parametro"] or row["parametro_exibicao"] or "").strip().lower(),
        ): row
        for row in existing_rows
    }

    for ordem, (operacao, controle, parametro) in enumerate(CATALOG_ITEMS, start=1):
        key = (operacao.strip().lower(), controle.strip().lower(), parametro.strip().lower())
        existing = existing_map.get(key)
        values = {
            "escopo": "central_tintas",
            "modulo": "central-tintas",
            "aba": "Ambos",
            "module_code": "central-tintas",
            "setor_tipo": "AMBOS",
            "operacao": operacao,
            "controle": controle,
            "parametro": parametro,
            "parametro_exibicao": parametro,
            "tipo_validacao": "nenhum",
            "ordem": ordem,
            "obrigatorio": True,
            "ativo": True,
            "frequencia": "DIARIO",
            "frequencia_tipo": "diario",
            "prioridade": "medio",
            "responsavel_padrao": "Central de Tintas",
            "turno_padrao": "TODOS",
            "observacao": None,
        }
        if existing is None:
            bind.execute(op_items.insert().values(**values))
            continue
        bind.execute(
            op_items.update()
            .where(op_items.c.id == existing["id"])
            .values(**values)
        )


def downgrade() -> None:
    # Seed operacional preservado por compatibilidade.
    pass
