from __future__ import annotations

from collections.abc import Generator
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.services.auth_service import require_admin
from app.models import (
    Base,
    CabinePinturaRelatorio,
    CentralTintasRelatorio,
    ItemED,
    Modelo,
    OperationalModuleItem,
    OperationalModuleRecord,
    OperationalShift,
    Responsavel,
    Setor,
    TemperaturaFornoLancamento,
    Turno,
    User,
    SHIFT_STATUS_CONCLUIDO,
)
from app.services.auth_service import hash_password
from app.services.ed_seed_data import DEFAULT_RESPONSAVEIS, DEFAULT_SETORES, DEFAULT_TURNOS, build_seed_items
from app.services import dashboard_service
from app.services import item_frequency_runtime_service
from app.services import operational_module_item_service
from app.services.operational_module_seed import build_operational_module_seed_items_runtime
from app.services.operational_module_service import (
    MODULE_STATUS_CONCLUIDO,
    MODULE_STATUS_EM_ANDAMENTO,
    get_module_config,
    get_or_create_master,
)
from app.services.shift_service import build_shift_detail
from app.services.sigilatura_service import _escorrimento_field_key, _evaluate_param_rule


@pytest.fixture()
def test_env() -> Generator[tuple[TestClient, sessionmaker], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)

    with testing_session_local() as session:
        session.add_all(Responsavel(**row) for row in DEFAULT_RESPONSAVEIS)
        session.add(Modelo(nome="HB20", codigo="HB20", ativo=True))
        session.add_all(Setor(**row) for row in DEFAULT_SETORES)
        session.add_all(Turno(**row) for row in DEFAULT_TURNOS)
        session.add(
            User(
                username="admin",
                full_name="Admin",
                password_hash=hash_password("123456"),
                is_admin=True,
                is_active=True,
            )
        )
        session.add_all(ItemED(**row) for row in build_seed_items())
        session.add_all(OperationalModuleItem(**row) for row in build_operational_module_seed_items_runtime())
        session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, testing_session_local

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def _create_shift_response(
    client: TestClient,
    *,
    data_referencia: str = "2026-04-17",
    turno: str = "1",
):
    payload = {
        "data_referencia": data_referencia,
        "turno": turno,
        "responsavel_pted": "Condutor PT/ED",
        "responsavel_lab": "Laboratorio",
    }
    return client.post("/turno-atual/iniciar", data=payload, follow_redirects=False)


def _create_shift(client: TestClient, *, data_referencia: str = "2026-04-17", turno: str = "1") -> None:
    response = _create_shift_response(client, data_referencia=data_referencia, turno=turno)
    assert response.status_code == 303


def _create_pt_shift(client: TestClient, *, data_referencia: str = "2026-04-17", turno: str = "1") -> None:
    payload = {
        "data_referencia": data_referencia,
        "turno": turno,
        "responsavel_pted": "Condutor PT/ED",
        "responsavel_lab": "Laboratorio",
    }
    response = client.post("/turnos-pt/iniciar", data=payload, follow_redirects=False)
    assert response.status_code == 303


def _create_sigilatura_shift(client: TestClient, *, data_referencia: str = "2026-04-17", turno: str = "1") -> None:
    payload = {
        "data_referencia": data_referencia,
        "turno": turno,
        "responsavel": "Operador Sigilatura",
    }
    response = client.post("/turnos-sigilatura/iniciar", data=payload, follow_redirects=False)
    assert response.status_code == 303


def _get_shift_id(session_factory: sessionmaker, *, data_referencia: str, turno: str) -> int:
    with session_factory() as session:
        shift = session.scalars(
            select(OperationalShift)
            .where(OperationalShift.data_referencia == date.fromisoformat(data_referencia))
            .where(OperationalShift.turno == turno)
        ).first()
        assert shift is not None
        return shift.id


def _login_admin(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"username": "admin", "password": "123456", "next_url": "/configuracoes"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_sigilatura_temperature_rule_accepts_plus_minus_tolerance() -> None:
    assert _evaluate_param_rule("150 +- 10 °C", "150") == ("DENTRO", "NAO")
    assert _evaluate_param_rule("150 +/- 10 °C", "140") == ("DENTRO", "NAO")
    assert _evaluate_param_rule("150 ± 10 °C", "161") == ("FORA", "SIM")


def test_sigilatura_escorrimento_catalog_uses_real_model_fields() -> None:
    item = SimpleNamespace(operacao="ESCORRIMENTO", controle="REAL ESTUFA MANUAL", ordem=6)

    assert _escorrimento_field_key(item, 6) == "real_estufa_manual"


def _enable_admin_override() -> None:
    app.dependency_overrides[require_admin] = lambda: object()


def _temperatura_payload(setor: str, *, data_referencia: str = "2026-04-17", outlier: bool = False) -> dict[str, str]:
    payload = {
        "data_referencia": data_referencia,
        "responsavel_nome_PTED": "Condutor PT/ED",
        "observacoes_setor_PTED": "PTED ok",
        "responsavel_nome_LABORATORIO": "Laboratorio",
        "observacoes_setor_LABORATORIO": "Lab ok",
    }
    defaults = {
        1: "90",
        2: "90",
        3: "130",
        4: "170",
        5: "160",
        6: "180",
        7: "180",
        8: "180",
        9: "180",
        10: "180",
        11: "180",
        12: "180",
    }
    for zona, value in defaults.items():
        payload[f"value_{setor}_{zona}"] = "210" if outlier and zona == 4 else value
    return payload


@pytest.mark.parametrize(
    "slug",
    [
        "/pt",
        "/pressao-filtros-pt",
        "/ed",
        "/temperatura-forno-ed",
        "/pressao-filtros-ed",
        "/tensao-retificadores-ed",
        "/poder-penetracao",
        "/espessura-ed",
        "/aspecto",
        "/rugosidade",
    ],
)
def test_module_hubs_are_history_only(test_env: tuple[TestClient, sessionmaker], slug: str) -> None:
    client, _ = test_env

    response = client.get(slug)

    assert response.status_code == 200
    assert "Conclu" in response.text
    assert "Em andamento" in response.text
    assert "Iniciar ciclo" not in response.text


def test_dashboard_priority_map_defaults_blank_priority_to_medio(test_env: tuple[TestClient, sessionmaker]) -> None:
    _, session_factory = test_env

    with session_factory() as session:
        item = session.scalars(select(OperationalModuleItem).limit(1)).first()
        assert item is not None
        item.prioridade = ""
        session.commit()
        priority_map = dashboard_service._load_item_priority_map(session)

    assert priority_map[item.id] == "medio"


def test_dashboard_priority_map_handles_missing_priority_column(
    test_env: tuple[TestClient, sessionmaker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session_factory = test_env

    class _Inspector:
        @staticmethod
        def get_columns(_table_name: str) -> list[dict[str, str]]:
            return [{"name": "id"}]

    monkeypatch.setattr(dashboard_service, "sa_inspect", lambda _bind: _Inspector())

    with session_factory() as session:
        priority_map = dashboard_service._load_item_priority_map(session)
        item_ids = session.scalars(select(OperationalModuleItem.id)).all()

    assert priority_map
    assert set(priority_map.keys()) == {int(item_id) for item_id in item_ids}
    assert set(priority_map.values()) == {"medio"}


def test_dashboard_defaults_to_today_when_no_date_is_provided(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert f'value="{date.today().isoformat()}"' in response.text
    assert "Dashboard do Dia" in response.text
    assert "Nenhum dado" in response.text


def test_sidebar_replaces_individual_operational_links_with_operacoes(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env

    response = client.get("/operacoes")

    assert response.status_code == 200
    assert '<span class="nav-label">Operações</span>' in response.text
    assert '<span class="nav-label">Central de Tintas</span>' not in response.text
    assert '<span class="nav-label">Cabine de Pintura</span>' not in response.text
    assert '<span class="nav-label">Sigilatura</span>' not in response.text


def test_operacoes_page_aggregates_daily_modules(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    reference_date = "2026-05-02"
    _create_shift(client, data_referencia=reference_date, turno="1")
    _create_pt_shift(client, data_referencia=reference_date, turno="2")
    _create_sigilatura_shift(client, data_referencia=reference_date, turno="3")

    response = client.get(f"/operacoes?data_referencia={reference_date}")

    assert response.status_code == 200
    assert "Operações da Pintura" in response.text
    assert "02/05/2026" in response.text
    assert "PT" in response.text
    assert "ED" in response.text
    assert "Sigilatura" in response.text
    assert "Central de Tintas" in response.text
    assert "Cabine de Pintura" in response.text
    assert "Iniciar turno" in response.text


def test_operacoes_start_route_creates_central_tintas_relatorio(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env

    response = client.post(
        "/operacoes/iniciar",
        data={
            "module_code": "central-tintas",
            "data_referencia": "2026-05-03",
            "turno": "1",
            "responsavel": "Condutor PT/ED",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    with session_factory() as session:
        relatorio = session.scalars(select(CentralTintasRelatorio)).first()
        assert relatorio is not None
        assert response.headers["location"] == f"/central-tintas/{relatorio.id}"


def test_dashboard_aggregates_all_shifts_for_selected_day(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    reference_date = "2026-04-28"
    _create_shift(client, data_referencia=reference_date, turno="1")
    _create_pt_shift(client, data_referencia=reference_date, turno="2")
    _create_sigilatura_shift(client, data_referencia=reference_date, turno="3")

    response = client.get(f"/dashboard?data_referencia={reference_date}")

    assert response.status_code == 200
    assert "Resumo di" in response.text
    assert "CONTROL PLAN - GOIANA" in response.text
    assert "28/04/2026" in response.text
    assert "Realizado/Iniciado" in response.text
    assert "Prioridades" in response.text
    assert "SIGILATURA" in response.text
    assert "Selecionar turno" not in response.text


def test_operational_module_item_frequency_update_service(test_env: tuple[TestClient, sessionmaker]) -> None:
    _, session_factory = test_env

    with session_factory() as session:
        item = session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "temperatura-forno-ed")
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).first()
        assert item is not None

        updated = operational_module_item_service.atualizar_frequencia_item(
            session,
            item.id,
            {"frequencia_tipo": "semanal", "dia_semana": 2, "dia_mes": 18},
        )

        assert updated.frequencia_tipo == "semanal"
        assert updated.dia_semana == 2
        assert updated.dia_mes is None


@pytest.mark.parametrize(
    ("item", "reference_date", "expected"),
    [
        (SimpleNamespace(frequencia_tipo="diario", dia_semana=None, dia_mes=None, frequencia=None), date(2026, 4, 21), True),
        (SimpleNamespace(frequencia_tipo="semanal", dia_semana=1, dia_mes=None, frequencia=None), date(2026, 4, 21), True),
        (SimpleNamespace(frequencia_tipo="semanal", dia_semana=2, dia_mes=None, frequencia=None), date(2026, 4, 21), False),
        (SimpleNamespace(frequencia_tipo="semanal", dia_semana=7, dia_mes=None, frequencia=None), date(2026, 4, 26), True),
        (SimpleNamespace(frequencia_tipo="mensal", dia_semana=None, dia_mes=21, frequencia=None), date(2026, 4, 21), True),
        (SimpleNamespace(frequencia_tipo="mensal", dia_semana=None, dia_mes=20, frequencia=None), date(2026, 4, 21), False),
        (SimpleNamespace(frequencia_tipo="sob_demanda", dia_semana=None, dia_mes=None, frequencia=None), date(2026, 4, 21), False),
        (SimpleNamespace(frequencia_tipo=None, dia_semana=None, dia_mes=None, frequencia=None), date(2026, 4, 21), True),
    ],
)
def test_is_item_applicable_on_date(item: SimpleNamespace, reference_date: date, expected: bool) -> None:
    assert item_frequency_runtime_service.is_item_applicable_on_date(item, reference_date) is expected


def test_calculate_row_progress_uses_only_applicable_rows() -> None:
    rows = [
        {"is_applicable": True, "applicability_state": "applicable", "value": "1", "flag": False},
        {"is_applicable": True, "applicability_state": "applicable", "value": "2", "flag": False},
        {"is_applicable": True, "applicability_state": "applicable", "value": "3", "flag": False},
        {"is_applicable": True, "applicability_state": "applicable", "value": "4", "flag": False},
        {"is_applicable": True, "applicability_state": "applicable", "value": "", "flag": False},
        {"is_applicable": True, "applicability_state": "applicable", "value": "", "flag": False},
        {"is_applicable": True, "applicability_state": "applicable", "value": "", "flag": False},
        {"is_applicable": False, "applicability_state": "not_applicable", "value": "", "flag": False},
        {"is_applicable": False, "applicability_state": "not_applicable", "value": "", "flag": False},
        {"is_applicable": False, "applicability_state": "on_demand", "value": "", "flag": False},
    ]

    summary = item_frequency_runtime_service.calculate_row_progress(rows)

    assert summary["total"] == 7
    assert summary["preenchidos"] == 4
    assert summary["percentual"] == 57
    assert summary["not_applicable_count"] == 2
    assert summary["on_demand_count"] == 1


def test_calculate_row_progress_handles_no_applicable_rows() -> None:
    summary = item_frequency_runtime_service.calculate_row_progress(
        [
            {"is_applicable": False, "applicability_state": "not_applicable", "value": "", "flag": False},
            {"is_applicable": False, "applicability_state": "on_demand", "value": "", "flag": False},
        ]
    )

    assert summary["total"] == 0
    assert summary["preenchidos"] == 0
    assert summary["percentual"] == 100
    assert summary["status_text"] == "Sem itens aplicáveis hoje"


def test_resolve_item_applicability_honors_override_statuses() -> None:
    reference_date = date(2026, 4, 21)

    diario = SimpleNamespace(frequencia_tipo="diario", dia_semana=None, dia_mes=None, frequencia=None)
    sob_demanda = SimpleNamespace(frequencia_tipo="sob_demanda", dia_semana=None, dia_mes=None, frequencia=None)
    semanal_fora = SimpleNamespace(frequencia_tipo="semanal", dia_semana=4, dia_mes=None, frequencia=None)

    resolved_not_applicable = item_frequency_runtime_service.resolve_item_applicability(
        diario, reference_date, "not_applicable"
    )
    resolved_applicable_on_demand = item_frequency_runtime_service.resolve_item_applicability(
        sob_demanda, reference_date, "applicable"
    )
    resolved_applicable_weekly = item_frequency_runtime_service.resolve_item_applicability(
        semanal_fora, reference_date, "applicable"
    )
    resolved_dispensed = item_frequency_runtime_service.resolve_item_applicability(
        diario, reference_date, "dispensed"
    )

    assert resolved_not_applicable["is_applicable"] is False
    assert resolved_not_applicable["affects_progress"] is False
    assert resolved_not_applicable["applicability_label"] == "Não aplicável neste turno"

    assert resolved_applicable_on_demand["is_applicable"] is True
    assert resolved_applicable_on_demand["affects_progress"] is True
    assert resolved_applicable_on_demand["applicability_label"] == "Aplicável neste turno"

    assert resolved_applicable_weekly["is_applicable"] is True
    assert resolved_dispensed["is_applicable"] is False
    assert resolved_dispensed["applicability_label"] == "Dispensado no turno"


def test_configuracoes_frequencias_page_loads_for_admin(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    _enable_admin_override()

    response = client.get("/configuracoes/frequencias", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/configuracoes/modulos-itens"
    return
    assert "Selecione um módulo" in response.text
    assert response.headers["location"] == "/configuracoes/modulos-itens"


def test_unified_module_items_admin_page_loads_for_admin(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    _enable_admin_override()

    response = client.get("/configuracoes/modulos-itens")

    assert response.status_code == 200
    assert "data-module-admin-page" in response.text
    assert "Temperatura Forno" in response.text
    assert "data-save-module" in response.text


def test_unified_module_items_admin_page_supports_central_tintas_area(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    _enable_admin_override()

    response = client.get("/configuracoes/modulos-itens?area=central-tintas&modulo=central-tintas")

    assert response.status_code == 200
    assert 'data-selected-area="central-tintas"' in response.text
    assert 'data-selected-module="central-tintas"' in response.text
    assert "Central de Tintas" in response.text
    assert 'data-field="item_nome"' in response.text


def test_unified_module_items_admin_page_supports_cabine_pintura_area_and_abas(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    _enable_admin_override()

    response = client.get("/configuracoes/modulos-itens?area=cabine-pintura&modulo=cabine-pintura&aba=TOP%20COAT")

    assert response.status_code == 200
    assert 'data-selected-area="cabine-pintura"' in response.text
    assert 'data-selected-module="cabine-pintura"' in response.text
    assert "Cabine de Pintura" in response.text
    assert "TOP COAT" in response.text
    assert "TEMPERATURA FORNO" in response.text
    assert "DATA PAQ" in response.text
    assert 'data-field="aba"' in response.text


def test_unified_module_items_partial_changes_module_tab(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    _enable_admin_override()

    response = client.get("/configuracoes/modulos-itens/temperatura-forno-ed")

    assert response.status_code == 200
    assert "Zona 1" in response.text
    assert "data-col-frequencia" in response.text
    assert "Par&acirc;metro" not in response.text
    assert 'data-col-parametro' not in response.text


def test_unified_module_items_ed_shows_operacao_and_controle_inputs(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    _enable_admin_override()

    response = client.get("/configuracoes/modulos-itens/ed")

    assert response.status_code == 200
    assert 'data-field="operacao" data-editable data-inline-input' in response.text
    assert 'data-field="controle" data-editable data-inline-input' in response.text


def test_configuracoes_frequencias_update_endpoint_saves_item(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _enable_admin_override()

    with session_factory() as session:
        item = session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "temperatura-forno-ed")
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).first()
        assert item is not None
        item_id = item.id

    response = client.post(
        f"/configuracoes/frequencias/{item_id}",
        json={"frequencia_tipo": "mensal", "dia_semana": None, "dia_mes": 12},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}

    with session_factory() as session:
        saved = session.get(OperationalModuleItem, item_id)
        assert saved is not None
        assert saved.frequencia_tipo == "mensal"
        assert saved.dia_semana is None
        assert saved.dia_mes == 12


def test_module_items_batch_updates_existing_item_fields(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _enable_admin_override()

    with session_factory() as session:
        item = session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "temperatura-forno-ed")
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).first()
        assert item is not None
        item_id = item.id
        parametro_original = item.parametro

    response = client.post(
        "/configuracoes/modulos-itens/temperatura-forno-ed/batch",
        json={
            "rows": [
                {
                    "id": item_id,
                    "controle": "Zona Principal",
                    "operacao": "",
                    "setor_tipo": "PTED",
                    "parametro": "100 a 140 C",
                    "frequencia_tipo": "mensal",
                    "dia_semana": None,
                    "dia_mes": 7,
                    "ordem": 44,
                    "ativo": False,
                }
            ],
            "delete_ids": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True

    with session_factory() as session:
        saved = session.get(OperationalModuleItem, item_id)
        assert saved is not None
        assert saved.controle == "Zona Principal"
        assert saved.parametro == parametro_original
        assert saved.frequencia_tipo == "mensal"
        assert saved.dia_mes == 7
        assert saved.ordem == 44
        assert saved.ativo is False


def test_module_items_batch_accepts_legacy_sunday_weekday_value(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _enable_admin_override()

    with session_factory() as session:
        item = session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "temperatura-forno-ed")
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).first()
        assert item is not None
        item_id = item.id

    response = client.post(
        "/configuracoes/modulos-itens/temperatura-forno-ed/batch",
        json={
            "rows": [
                {
                    "id": item_id,
                    "controle": "Zona Principal",
                    "operacao": "",
                    "setor_tipo": "PTED",
                    "parametro": "100 a 140 C",
                    "frequencia_tipo": "semanal",
                    "dia_semana": 7,
                    "dia_mes": None,
                    "ordem": 44,
                    "ativo": True,
                }
            ],
            "delete_ids": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True

    with session_factory() as session:
        saved = session.get(OperationalModuleItem, item_id)
        assert saved is not None
        assert saved.frequencia_tipo == "semanal"
        assert saved.dia_semana == 6


def test_module_items_batch_can_update_weekday_to_monday(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _enable_admin_override()

    with session_factory() as session:
        item = session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "ed")
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).first()
        assert item is not None
        item.frequencia_tipo = "semanal"
        item.dia_semana = 1
        item.dia_mes = None
        session.commit()
        item_id = item.id
        setor_tipo = item.setor_tipo
        operacao = item.operacao or ""
        controle = item.controle
        ordem = item.ordem
        ativo = item.ativo

    response = client.post(
        "/configuracoes/modulos-itens/ed/batch",
        json={
            "rows": [
                {
                    "id": item_id,
                    "controle": controle,
                    "operacao": operacao,
                    "setor_tipo": setor_tipo,
                    "frequencia_tipo": "semanal",
                    "dia_semana": 0,
                    "dia_mes": None,
                    "ordem": ordem,
                    "ativo": ativo,
                }
            ],
            "delete_ids": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True

    with session_factory() as session:
        saved = session.get(OperationalModuleItem, item_id)
        assert saved is not None
        assert saved.frequencia_tipo == "semanal"
        assert saved.dia_semana == 0


def test_module_items_batch_ed_weekly_without_weekday_does_not_fail(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _enable_admin_override()

    with session_factory() as session:
        item = session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "ed")
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).first()
        assert item is not None
        item.frequencia_tipo = "semanal"
        item.dia_semana = None
        item.dia_mes = None
        session.commit()
        item_id = item.id
        setor_tipo = item.setor_tipo
        operacao = item.operacao or ""
        controle = item.controle
        ordem = item.ordem
        ativo = item.ativo

    response = client.post(
        "/configuracoes/modulos-itens/ed/batch",
        json={
            "rows": [
                {
                    "id": item_id,
                    "controle": controle,
                    "operacao": operacao,
                    "setor_tipo": setor_tipo,
                    "frequencia_tipo": "semanal",
                    "dia_semana": None,
                    "dia_mes": None,
                    "ordem": ordem,
                    "ativo": ativo,
                }
            ],
            "delete_ids": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True

    with session_factory() as session:
        saved = session.get(OperationalModuleItem, item_id)
        assert saved is not None
        assert saved.frequencia_tipo == "semanal"
        assert saved.dia_semana == 0
        assert saved.dia_mes is None


def test_module_items_batch_creates_new_item(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _enable_admin_override()

    response = client.post(
        "/configuracoes/modulos-itens/poder-penetracao/batch",
        json={
            "rows": [
                {
                    "id": None,
                    "controle": "Novo ponto",
                    "operacao": "",
                    "setor_tipo": "PTED",
                    "parametro": ">= 8,1",
                    "frequencia_tipo": "semanal",
                    "dia_semana": 2,
                    "dia_mes": None,
                    "ordem": 99,
                    "ativo": True,
                }
            ],
            "delete_ids": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["created_count"] == 1

    with session_factory() as session:
        created = session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "poder-penetracao")
            .where(OperationalModuleItem.controle == "Novo ponto")
        ).first()
        assert created is not None
        assert created.frequencia_tipo == "semanal"
        assert created.dia_semana == 2


def test_module_items_batch_deletes_item_group(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _enable_admin_override()

    with session_factory() as session:
        item = session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "temperatura-forno-ed")
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).first()
        assert item is not None
        item_id = item.id

    response = client.post(
        "/configuracoes/modulos-itens/temperatura-forno-ed/batch",
        json={"rows": [], "delete_ids": [item_id]},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True

    with session_factory() as session:
        deleted = session.get(OperationalModuleItem, item_id)
        assert deleted is None


def test_old_modulos_itens_list_redirects_to_unified_page(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    _enable_admin_override()

    response = client.get("/cadastros/modulos-itens?module_code=rugosidade", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/configuracoes/modulos-itens?modulo=rugosidade"


def test_historico_geral_page_is_removed(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env

    response = client.get("/historico-geral")

    assert response.status_code == 404


def test_legacy_module_report_route_is_removed(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-25", turno="1")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-25", turno="1")

    save_response = client.post(
        f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/PTED/salvar",
        data={**_temperatura_payload("PTED", data_referencia="2026-04-25"), "submit_action": "salvar"},
        follow_redirects=False,
    )
    assert save_response.status_code == 303

    with session_factory() as session:
        record = session.scalars(
            select(OperationalModuleRecord)
            .where(OperationalModuleRecord.module_code == "temperatura-forno-ed")
            .where(OperationalModuleRecord.shift_id == shift_id)
        ).first()
        assert record is not None
        record_id = record.id

    response = client.get(f"/temperatura-forno-ed/registros/{record_id}/relatorio")

    assert response.status_code == 404


def test_shift_detail_excludes_non_applicable_items_from_pending_progress(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-22", turno="1")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-22", turno="1")

    with session_factory() as session:
        session.query(OperationalModuleItem).filter(
            OperationalModuleItem.module_code == "temperatura-forno-ed"
        ).update(
            {
                OperationalModuleItem.frequencia_tipo: "mensal",
                OperationalModuleItem.dia_mes: 1,
                OperationalModuleItem.dia_semana: None,
            },
            synchronize_session=False,
        )
        session.commit()

        shift = session.get(OperationalShift, shift_id)
        assert shift is not None
        detail = build_shift_detail(session, shift)

    temperatura = next(module for module in detail["modules"] if module["code"] == "temperatura-forno-ed")
    assert temperatura["pted_progress"]["total"] == 0
    assert temperatura["progress_percent"] == 100
    assert temperatura["status_geral_label"] == "Sem itens aplicáveis hoje"
    assert all(module["code"] != "temperatura-forno-ed" for module in detail["pending_modules"])


def test_shift_detail_uses_override_to_force_applicable_item(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-22", turno="1")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-22", turno="1")

    with session_factory() as session:
        session.query(OperationalModuleItem).filter(
            OperationalModuleItem.module_code == "temperatura-forno-ed"
        ).update(
            {
                OperationalModuleItem.frequencia_tipo: "mensal",
                OperationalModuleItem.dia_mes: 1,
                OperationalModuleItem.dia_semana: None,
            },
            synchronize_session=False,
        )
        session.commit()

        item = session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "temperatura-forno-ed")
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).first()
        assert item is not None

        item_frequency_runtime_service.save_item_applicability_override(session, shift_id, item.id, "applicable")
        shift = session.get(OperationalShift, shift_id)
        assert shift is not None
        detail = build_shift_detail(session, shift)

    temperatura = next(module for module in detail["modules"] if module["code"] == "temperatura-forno-ed")
    assert temperatura["pted_progress"]["total"] == 1
    assert temperatura["progress_percent"] == 0
    assert any(module["code"] == "temperatura-forno-ed" for module in detail["pending_modules"])


def test_shift_detail_preserves_manually_concluded_status(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-22", turno="2")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-22", turno="2")

    with session_factory() as session:
        shift = session.get(OperationalShift, shift_id)
        assert shift is not None
        shift.status_geral = SHIFT_STATUS_CONCLUIDO
        session.commit()

        detail = build_shift_detail(session, shift)

    assert detail["status_geral"] == SHIFT_STATUS_CONCLUIDO


def test_turno_item_applicability_override_route_updates_progress(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-22", turno="1")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-22", turno="1")

    with session_factory() as session:
        item = session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "poder-penetracao")
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).first()
        assert item is not None
        item_id = item.id
        item.frequencia_tipo = "sob_demanda"
        session.commit()

    response = client.post(
        f"/turnos/execution/{shift_id}/items/{item_id}/applicability",
        json={"override_status": "applicable", "reason": "Exigido no turno"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["resolved_label"] == "Aplicável neste turno"
    assert payload["affects_progress"] is True
    assert payload["module_progress"]["code"] == "poder-penetracao"
    assert payload["module_progress"]["pted_progress"]["total"] >= 1


def test_turno_execution_hides_conclude_shift_controls_when_shift_is_concluded(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-23", turno="2")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-23", turno="2")

    conclude_response = client.post(f"/turnos/{shift_id}/concluir", follow_redirects=False)
    assert conclude_response.status_code == 303

    response = client.get(f"/turnos/{shift_id}")

    assert response.status_code == 200
    assert "Concluir turno" not in response.text
    assert "data-open-close-shift-modal" not in response.text
    assert "closeShiftModal" not in response.text


def test_turno_visualizacao_recovers_legacy_retificador_context_without_group(
    test_env: tuple[TestClient, sessionmaker],
) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-23", turno="2")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-23", turno="2")

    with session_factory() as session:
        shift = session.get(OperationalShift, shift_id)
        assert shift is not None
        config = get_module_config("tensao-retificadores-ed")
        master = get_or_create_master(
            session,
            config,
            {
                "data_referencia": date.fromisoformat("2026-04-23"),
                "turno": "2",
                "grupo_retificador": "grupo_1",
            },
            shift_id=shift_id,
        )
        master.context_data = {
            "data_referencia": "2026-04-23",
            "turno": "2",
        }
        session.commit()

    response = client.get(f"/turnos/{shift_id}/visualizar?modulo=tensao-retificadores-ed")

    assert response.status_code == 200
    assert "Tensão dos Retificadores" in response.text


def test_module_start_route_redirects_to_turnos_without_creating_record(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env

    response = client.post("/ed/iniciar", data={"data_referencia": "2026-04-17", "turno": "1", "tipo_dia": "normal"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/turno-atual"
    with session_factory() as session:
        assert session.scalars(select(OperationalModuleRecord)).first() is None


def test_save_sector_without_shift_link_is_blocked(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env

    response = client.post(
        "/temperatura-forno-ed/setores/PTED/salvar",
        data={**_temperatura_payload("PTED", data_referencia="2026-04-24"), "submit_action": "salvar"},
    )

    assert response.status_code == 400
    assert "tela principal do turno" in response.text.lower()
    with session_factory() as session:
        assert session.scalars(select(OperationalModuleRecord)).first() is None


def test_turno_atual_is_the_new_turns_index(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env

    response = client.get("/turno-atual")

    assert response.status_code == 200
    assert "Turnos" in response.text
    assert "Iniciar turno" in response.text


def test_central_tintas_uses_turno_hub_layout(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env

    response = client.get("/central-tintas")

    assert response.status_code == 200
    assert "Iniciar turno" in response.text
    assert "Em andamento" in response.text
    assert "Concluidos" in response.text


def test_cabine_pintura_uses_turno_hub_layout(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env

    response = client.get("/cabine-pintura")

    assert response.status_code == 200
    assert "Iniciar turno" in response.text
    assert "Em andamento" in response.text
    assert "Concluidos" in response.text


def test_cabine_pintura_start_creates_relatorio_and_redirects(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env

    response = client.post(
        "/cabine-pintura/iniciar",
        data={
            "data_referencia": "2026-05-02",
            "turno": "1",
            "responsavel": "Condutor PT/ED",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    with session_factory() as session:
        relatorio = session.scalars(select(CabinePinturaRelatorio)).first()
        assert relatorio is not None
        assert len(relatorio.itens) > 0
        assert response.headers["location"] == f"/cabine-pintura/{relatorio.id}"


def test_cabine_pintura_execution_blocks_conclusion_with_pending_items(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    start_response = client.post(
        "/cabine-pintura/iniciar",
        data={
            "data_referencia": "2026-05-03",
            "turno": "2",
            "responsavel": "Laboratorio",
        },
        follow_redirects=False,
    )
    assert start_response.status_code == 303

    with session_factory() as session:
        relatorio = session.scalars(select(CabinePinturaRelatorio)).first()
        assert relatorio is not None
        relatorio_id = relatorio.id

    save_response = client.post(
        f"/cabine-pintura/{relatorio_id}/salvar",
        data={
            "item_1_valor": "22",
            "submit_action": "concluir",
        },
        follow_redirects=False,
    )
    assert save_response.status_code == 303
    assert save_response.headers["location"].startswith(f"/cabine-pintura/{relatorio_id}?error=")

    response = client.get(save_response.headers["location"], follow_redirects=True)

    assert response.status_code == 200
    assert "Existem itens pendentes" in response.text


def test_cabine_pintura_execution_can_conclude_and_redirect_to_view(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    start_response = client.post(
        "/cabine-pintura/iniciar",
        data={
            "data_referencia": "2026-05-04",
            "turno": "3",
            "responsavel": "Laboratorio",
        },
        follow_redirects=False,
    )
    assert start_response.status_code == 303

    with session_factory() as session:
        relatorio = session.scalars(select(CabinePinturaRelatorio)).first()
        assert relatorio is not None
        relatorio_id = relatorio.id
        item_ids = [item.id for item in relatorio.itens]

    payload = {"submit_action": "concluir"}
    for index, item_id in enumerate(item_ids, start=1):
        payload[f"item_{item_id}_valor"] = f"valor-{index}"
        payload[f"item_{item_id}_observacao"] = ""

    save_response = client.post(
        f"/cabine-pintura/{relatorio_id}/salvar",
        data=payload,
        follow_redirects=False,
    )
    assert save_response.status_code == 303
    assert save_response.headers["location"] == f"/cabine-pintura/{relatorio_id}"

    response = client.get(f"/cabine-pintura/{relatorio_id}", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == f"/cabine-pintura/{relatorio_id}/visualizar"


def test_central_tintas_start_creates_relatorio_and_redirects(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env

    response = client.post(
        "/central-tintas/iniciar",
        data={
            "data_referencia": "2026-04-28",
            "turno": "1",
            "responsavel": "Condutor PT/ED",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    with session_factory() as session:
        relatorio = session.scalars(select(CentralTintasRelatorio)).first()
        assert relatorio is not None
        assert len(relatorio.itens) >= 70
        assert response.headers["location"] == f"/central-tintas/{relatorio.id}"


def test_central_tintas_execution_blocks_conclusion_with_pending_items(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    start_response = client.post(
        "/central-tintas/iniciar",
        data={
            "data_referencia": "2026-04-29",
            "turno": "2",
            "responsavel": "Laboratorio",
        },
        follow_redirects=False,
    )
    assert start_response.status_code == 303

    with session_factory() as session:
        relatorio = session.scalars(select(CentralTintasRelatorio)).first()
        assert relatorio is not None
        relatorio_id = relatorio.id

    save_response = client.post(
        f"/central-tintas/{relatorio_id}/salvar",
        data={
            "item_1_valor": "22",
            "submit_action": "concluir",
        },
        follow_redirects=False,
    )
    assert save_response.status_code == 303
    assert save_response.headers["location"].startswith(f"/central-tintas/{relatorio_id}?error=")

    response = client.get(save_response.headers["location"], follow_redirects=True)

    assert response.status_code == 200
    assert "Existem itens pendentes" in response.text


def test_central_tintas_execution_can_conclude_and_redirect_to_view(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    start_response = client.post(
        "/central-tintas/iniciar",
        data={
            "data_referencia": "2026-04-30",
            "turno": "3",
            "responsavel": "Laboratorio",
        },
        follow_redirects=False,
    )
    assert start_response.status_code == 303

    with session_factory() as session:
        relatorio = session.scalars(select(CentralTintasRelatorio)).first()
        assert relatorio is not None
        relatorio_id = relatorio.id
        item_ids = [item.id for item in relatorio.itens]

    payload = {"submit_action": "concluir"}
    for index, item_id in enumerate(item_ids, start=1):
        payload[f"item_{item_id}_valor"] = f"valor-{index}"
        payload[f"item_{item_id}_observacao"] = ""

    save_response = client.post(
        f"/central-tintas/{relatorio_id}/salvar",
        data=payload,
        follow_redirects=False,
    )
    assert save_response.status_code == 303
    assert save_response.headers["location"] == f"/central-tintas/{relatorio_id}"

    response = client.get(f"/central-tintas/{relatorio_id}", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == f"/central-tintas/{relatorio_id}/visualizar"


def test_dashboard_includes_central_tintas_module_card(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    client.post(
        "/central-tintas/iniciar",
        data={
            "data_referencia": "2026-05-01",
            "turno": "1",
            "responsavel": "Condutor PT/ED",
        },
        follow_redirects=False,
    )

    with session_factory() as session:
        relatorio = session.scalars(select(CentralTintasRelatorio)).first()
        assert relatorio is not None
        relatorio_id = relatorio.id
        item_ids = [item.id for item in relatorio.itens[:3]]

    payload = {"submit_action": "salvar"}
    for item_id in item_ids:
        payload[f"item_{item_id}_valor"] = "ok"

    client.post(
        f"/central-tintas/{relatorio_id}/salvar",
        data=payload,
        follow_redirects=False,
    )

    response = client.get("/dashboard?data_referencia=2026-05-01")

    assert response.status_code == 200
    assert "Central de Tintas" in response.text
    assert "/central-tintas?tab=concluidos" in response.text


def test_dashboard_includes_cabine_pintura_module_card(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    client.post(
        "/cabine-pintura/iniciar",
        data={
            "data_referencia": "2026-05-05",
            "turno": "1",
            "responsavel": "Condutor PT/ED",
        },
        follow_redirects=False,
    )

    with session_factory() as session:
        relatorio = session.scalars(select(CabinePinturaRelatorio)).first()
        assert relatorio is not None
        relatorio_id = relatorio.id
        item_ids = [item.id for item in relatorio.itens[:3]]

    payload = {"submit_action": "salvar"}
    for item_id in item_ids:
        payload[f"item_{item_id}_valor"] = "ok"

    client.post(
        f"/cabine-pintura/{relatorio_id}/salvar",
        data=payload,
        follow_redirects=False,
    )

    response = client.get("/dashboard?data_referencia=2026-05-05")

    assert response.status_code == 200
    assert "Cabine de Pintura" in response.text
    assert "/cabine-pintura?tab=concluidos" in response.text


def test_turno_iniciar_creates_master_and_redirects_to_execution(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env

    response = _create_shift_response(client, data_referencia="2026-04-18", turno="2")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-18", turno="2")

    assert response.status_code == 303
    assert response.headers["location"] == f"/turnos/{shift_id}"


def test_turnos_index_lists_created_shift(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-18", turno="2")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-18", turno="2")

    response = client.get("/turno-atual")

    assert response.status_code == 200
    assert f"/turnos/{shift_id}" in response.text
    assert "Abrir turno" in response.text


def test_turnos_ed_alias_redirects_to_turno_atual(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env

    response = client.get("/turnos-ed", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/turno-atual"


def test_turno_execution_shows_browser_tabs_and_no_individual_start_button(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-19", turno="1")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-19", turno="1")

    response = client.get(f"/turnos/{shift_id}")

    assert response.status_code == 200
    assert "Temperatura Forno" in response.text
    assert "Pressão dos Filtros" in response.text or "PressÃ£o dos Filtros ED" in response.text
    assert "Tensão dos Retificadores" in response.text or "TensÃ£o dos Retificadores ED" in response.text
    assert "Poder de Penetração" in response.text or "Poder de PenetraÃ§Ã£o" in response.text
    assert "Iniciar modulo" not in response.text
    assert "Iniciar pelo Turno Atual" not in response.text


def test_turno_execution_embeds_extra_context_fields_inside_module(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-20", turno="2")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-20", turno="2")

    response = client.get(f"/turnos/{shift_id}?modulo=ed")

    assert response.status_code == 200
    assert "Tipo do dia" not in response.text
    assert "Condutor PT/ED" in response.text
    assert "Laboratorio" in response.text
    assert "Iniciar pelo Turno Atual" not in response.text


def test_turno_execution_hides_laboratorio_tab_for_pted_only_modules(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-20", turno="2")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-20", turno="2")

    response = client.get(f"/turnos/{shift_id}?modulo=temperatura-forno-ed")

    assert response.status_code == 200
    assert 'data-tab-target="LABORATORIO"' not in response.text
    assert f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/LABORATORIO/salvar" not in response.text
    assert f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/PTED/salvar" in response.text


def test_turno_execution_shows_only_laboratorio_tab_for_rugosidade(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-20", turno="2")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-20", turno="2")

    response = client.get(f"/turnos/{shift_id}?modulo=rugosidade")

    assert response.status_code == 200
    assert 'data-tab-target="PTED"' not in response.text
    assert f"/turnos/{shift_id}/modulos/rugosidade/setores/PTED/salvar" not in response.text
    assert f"/turnos/{shift_id}/modulos/rugosidade/setores/LABORATORIO/salvar" in response.text
    with session_factory() as session:
        item = session.scalars(
            select(OperationalModuleItem).where(OperationalModuleItem.module_code == "rugosidade")
        ).first()
        assert item is not None
        assert item.setor_tipo == "LABORATORIO"


def test_legacy_shift_module_route_redirects_to_new_execution_workspace(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-21", turno="3")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-21", turno="3")

    response = client.get(f"/turno-atual/{shift_id}/modulos/ed", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == f"/turnos/{shift_id}?modulo=ed"


def test_turno_sector_save_creates_record_with_shift_id(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-22", turno="1")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-22", turno="1")

    response = client.post(
        f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/PTED/salvar",
        data={**_temperatura_payload("PTED", data_referencia="2026-04-22"), "submit_action": "salvar"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/turnos/{shift_id}?modulo=temperatura-forno-ed&setor=PTED"
    with session_factory() as session:
        record = session.scalars(
            select(OperationalModuleRecord)
            .where(OperationalModuleRecord.module_code == "temperatura-forno-ed")
            .where(OperationalModuleRecord.shift_id == shift_id)
        ).first()
        assert record is not None
        assert record.shift_id == shift_id
        assert record.data_referencia == date.fromisoformat("2026-04-22")
        assert record.status_geral == MODULE_STATUS_EM_ANDAMENTO


def test_turno_sector_save_concludes_pted_only_module_without_lab(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-22", turno="1")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-22", turno="1")

    response = client.post(
        f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/PTED/salvar",
        data={**_temperatura_payload("PTED", data_referencia="2026-04-22"), "submit_action": "concluir"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    with session_factory() as session:
        record = session.scalars(
            select(OperationalModuleRecord)
            .where(OperationalModuleRecord.module_code == "temperatura-forno-ed")
            .where(OperationalModuleRecord.shift_id == shift_id)
        ).first()
        assert record is not None
        assert record.status_geral == MODULE_STATUS_CONCLUIDO


def test_module_hub_shows_link_back_to_shift_execution(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-23", turno="2")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-23", turno="2")
    client.post(
        f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/PTED/salvar",
        data={**_temperatura_payload("PTED", data_referencia="2026-04-23"), "submit_action": "salvar"},
        follow_redirects=False,
    )

    response = client.get("/temperatura-forno-ed?tab=andamento")

    assert response.status_code == 200
    assert "execução do turno" in response.text.lower()


def test_shift_linked_checklist_redirects_back_to_execution_workspace(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-24", turno="1")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-24", turno="1")
    client.post(
        f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/PTED/salvar",
        data={**_temperatura_payload("PTED", data_referencia="2026-04-24"), "submit_action": "salvar"},
        follow_redirects=False,
    )

    with session_factory() as session:
        record = session.scalars(
            select(OperationalModuleRecord)
            .where(OperationalModuleRecord.module_code == "temperatura-forno-ed")
            .where(OperationalModuleRecord.shift_id == shift_id)
        ).first()
        assert record is not None
        record_id = record.id

    response = client.get(f"/temperatura-forno-ed/registros/{record_id}/checklist", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == f"/turnos/{shift_id}?modulo=temperatura-forno-ed"


def test_shift_linked_record_appears_in_historical_hub_only_as_consulta(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-25", turno="1")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-25", turno="1")
    client.post(
        f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/PTED/salvar",
        data={**_temperatura_payload("PTED", data_referencia="2026-04-25"), "submit_action": "salvar"},
        follow_redirects=False,
    )

    response = client.get("/temperatura-forno-ed")

    assert response.status_code == 200
    assert "Iniciar ciclo" not in response.text
    assert "Conclu" in response.text or "Em andamento" in response.text


def test_turno_sector_save_reuses_existing_shift_record(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-26", turno="1")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-26", turno="1")

    first = client.post(
        f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/PTED/salvar",
        data={**_temperatura_payload("PTED", data_referencia="2026-04-26"), "submit_action": "salvar"},
        follow_redirects=False,
    )
    second = client.post(
        f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/PTED/salvar",
        data={**_temperatura_payload("PTED", data_referencia="2026-04-26"), "submit_action": "salvar"},
        follow_redirects=False,
    )

    assert first.status_code == 303
    assert second.status_code == 303
    with session_factory() as session:
        records = session.scalars(
            select(OperationalModuleRecord)
            .where(OperationalModuleRecord.module_code == "temperatura-forno-ed")
            .where(OperationalModuleRecord.shift_id == shift_id)
        ).all()
        assert len(records) == 1


def test_turno_sector_save_reuses_existing_context_record_without_shift(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-17", turno="1")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-17", turno="1")

    with session_factory() as session:
        config = get_module_config("temperatura-forno-ed")
        orphan = get_or_create_master(session, config, {"data_referencia": date.fromisoformat("2026-04-17")})
        session.commit()
        orphan_id = orphan.id

    response = client.post(
        f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/PTED/salvar",
        data={**_temperatura_payload("PTED", data_referencia="2026-04-17"), "submit_action": "salvar"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    with session_factory() as session:
        records = session.scalars(
            select(OperationalModuleRecord)
            .where(OperationalModuleRecord.module_code == "temperatura-forno-ed")
            .where(OperationalModuleRecord.context_key == "temperatura-forno-ed|data_referencia=2026-04-17")
        ).all()
        assert len(records) == 1
        assert records[0].id == orphan_id
        assert records[0].shift_id == shift_id


def test_shift_linked_record_can_be_concluded_from_turno_execution(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    _create_shift(client, data_referencia="2026-04-27", turno="1")
    shift_id = _get_shift_id(session_factory, data_referencia="2026-04-27", turno="1")

    client.post(
        f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/PTED/salvar",
        data={**_temperatura_payload("PTED", data_referencia="2026-04-27"), "submit_action": "concluir"},
        follow_redirects=False,
    )
    response = client.post(
        f"/turnos/{shift_id}/modulos/temperatura-forno-ed/setores/LABORATORIO/salvar",
        data={**_temperatura_payload("LABORATORIO", data_referencia="2026-04-27"), "submit_action": "concluir"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    with session_factory() as session:
        record = session.scalars(
            select(OperationalModuleRecord)
            .where(OperationalModuleRecord.module_code == "temperatura-forno-ed")
            .where(OperationalModuleRecord.shift_id == shift_id)
        ).first()
        assert record is not None
        assert record.status_geral == MODULE_STATUS_CONCLUIDO


def test_legacy_detail_remains_available(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    with session_factory() as session:
        lancamento = TemperaturaFornoLancamento(
            data_referencia=date.fromisoformat("2026-04-16"),
            responsavel_nome="Operador legado",
            status="concluido",
            observacoes_gerais="Registro antigo",
            total_zonas_fora_padrao=1,
        )
        session.add(lancamento)
        session.commit()
        legacy_id = lancamento.id

    response = client.get(f"/temperatura-forno-ed/legado/{legacy_id}")

    assert response.status_code == 200
    assert "Registro antigo" in response.text
