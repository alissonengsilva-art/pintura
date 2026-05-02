"""backfill central tintas catalog rows from legacy fields

Revision ID: 20260502_0029
Revises: 20260502_0028
Create Date: 2026-05-02 13:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260502_0029"
down_revision = "20260502_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()

    relatorios = sa.Table("central_tintas_relatorios", metadata, autoload_with=bind)
    itens = sa.Table("central_tintas_itens", metadata, autoload_with=bind)
    op_items = sa.Table("operational_module_items", metadata, autoload_with=bind)

    controls = [
        ("Tinta", "tinta"),
        ("Lote", "lote"),
        ("pH", "ph"),
        ("Viscosidade", "viscosidade"),
        ("Sujidade", "sujidade"),
        ("Acoes corretivas", "acoes_corretivas"),
    ]

    # Resolve item ids from unified catalog once.
    catalog_rows = list(
        bind.execute(
            sa.select(op_items.c.id, op_items.c.controle, op_items.c.ordem)
            .where(op_items.c.ativo.is_(True))
            .where(op_items.c.escopo == "central_tintas")
            .where(op_items.c.modulo == "central-tintas")
            .order_by(op_items.c.ordem.asc(), op_items.c.id.asc())
        ).mappings()
    )
    if not catalog_rows:
        return

    control_to_item_id: dict[str, int] = {}
    for row in catalog_rows:
        key = str(row["controle"] or "").strip().lower()
        if key and key not in control_to_item_id:
            control_to_item_id[key] = int(row["id"])

    # Only backfill reports that still do not have catalog-linked rows.
    report_ids = [
        int(row[0])
        for row in bind.execute(sa.select(relatorios.c.id)).all()
    ]

    for report_id in report_ids:
        has_catalog = bind.execute(
            sa.select(sa.func.count())
            .select_from(itens)
            .where(itens.c.central_tintas_id == report_id)
            .where(itens.c.operational_module_item_id.is_not(None))
        ).scalar_one()
        if has_catalog:
            continue

        legacy_rows = list(
            bind.execute(
                sa.select(itens)
                .where(itens.c.central_tintas_id == report_id)
                .order_by(itens.c.id.asc())
            ).mappings()
        )
        if not legacy_rows:
            continue

        # Safe mode: backfill only reports with a single legacy row.
        if len(legacy_rows) != 1:
            continue

        legacy = legacy_rows[0]
        created_any = False
        for control_label, legacy_field in controls:
            raw_value = legacy.get(legacy_field)
            value = str(raw_value or "").strip()
            if not value:
                continue
            item_id = control_to_item_id.get(control_label.strip().lower())
            if item_id is None:
                continue

            bind.execute(
                itens.insert().values(
                    central_tintas_id=report_id,
                    operational_module_item_id=item_id,
                    controle=control_label,
                    valor=value,
                    observacao=None,
                    status="NAO_AVALIADO",
                )
            )
            created_any = True

        if created_any:
            # Leave legacy row untouched for audit/compatibility.
            pass


def downgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    itens = sa.Table("central_tintas_itens", metadata, autoload_with=bind)

    bind.execute(
        sa.delete(itens)
        .where(itens.c.operational_module_item_id.is_not(None))
        .where(itens.c.controle.in_(["Tinta", "Lote", "pH", "Viscosidade", "Sujidade", "Acoes corretivas"]))
    )
