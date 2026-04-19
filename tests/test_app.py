from __future__ import annotations

from collections.abc import Generator
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import (
    Base,
    ItemED,
    Modelo,
    OperationalModuleItem,
    OperationalModuleRecord,
    OperationalShift,
    Responsavel,
    Setor,
    TemperaturaFornoLancamento,
    Turno,
)
from app.services.ed_seed_data import DEFAULT_RESPONSAVEIS, DEFAULT_SETORES, DEFAULT_TURNOS, build_seed_items
from app.services.operational_module_seed import build_operational_module_seed_items_runtime
from app.services.operational_module_service import (
    MODULE_STATUS_CONCLUIDO,
    MODULE_STATUS_EM_ANDAMENTO,
    get_module_config,
    get_or_create_master,
)


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


def _get_shift_id(session_factory: sessionmaker, *, data_referencia: str, turno: str) -> int:
    with session_factory() as session:
        shift = session.scalars(
            select(OperationalShift)
            .where(OperationalShift.data_referencia == date.fromisoformat(data_referencia))
            .where(OperationalShift.turno == turno)
        ).first()
        assert shift is not None
        return shift.id


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
    assert "Em andamento" in response.text
    assert "Concluidos" in response.text


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
