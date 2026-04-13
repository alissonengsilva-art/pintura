from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import (
    Base,
    EDLancamento,
    ItemED,
    PressaoFiltrosLancamento,
    Responsavel,
    Setor,
    TensaoRetificadoresLancamento,
    TemperaturaFornoLancamento,
    Turno,
)
from app.services.dashboard_service import build_dashboard_snapshot, parse_dashboard_filters
from app.services.ed_seed_data import DEFAULT_RESPONSAVEIS, DEFAULT_SETORES, DEFAULT_TURNOS, build_seed_items
from app.services.ed_service import load_items_for_context


@pytest.fixture()
def test_env() -> Generator[tuple[TestClient, sessionmaker], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as session:
        session.add_all(Responsavel(**row) for row in DEFAULT_RESPONSAVEIS)
        session.add_all(Setor(**row) for row in DEFAULT_SETORES)
        session.add_all(Turno(**row) for row in DEFAULT_TURNOS)
        session.add_all(ItemED(**row) for row in build_seed_items())
        session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, TestingSessionLocal

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def _build_form_payload(
    session_factory: sessionmaker,
    setor: str,
    turno: str,
    submit_action: str,
    *,
    data_referencia: str = "2026-04-13",
    observacoes_gerais: str = "Lançamento de teste",
) -> dict[str, str | list[str]]:
    with session_factory() as session:
        items = load_items_for_context(session, setor, turno)

    assert items
    payload: dict[str, str | list[str]] = {
        "data_referencia": data_referencia,
        "tipo_dia": "normal",
        "setor": setor,
        "turno": turno,
        "responsavel_nome": "Laboratório" if setor == "Laboratório" else "Condutor PT/ED",
        "observacoes_gerais": observacoes_gerais,
        "submit_action": submit_action,
        "item_ids": [],
    }
    for item in items:
        payload["item_ids"].append(str(item.id))
        if item.parametro and (item.parametro.startswith("<") or item.parametro.startswith("<=")):
            payload[f"valor_{item.id}"] = "20"
        else:
            payload[f"valor_{item.id}"] = "23"
        payload[f"observacao_{item.id}"] = "ok"
    return payload


def _build_pressao_payload(
    turno: str,
    submit_action: str,
    *,
    data_referencia: str = "2026-04-13",
    responsavel_nome: str = "Condutor PT/ED",
    observacoes_gerais: str = "Leitura de pressão",
    alarm_filters: set[int] | None = None,
) -> dict[str, str]:
    alarm_filters = alarm_filters or set()
    payload: dict[str, str] = {
        "data_referencia": data_referencia,
        "turno": turno,
        "responsavel_nome": responsavel_nome,
        "observacoes_gerais": observacoes_gerais,
        "submit_action": submit_action,
    }
    for filtro_numero in range(1, 25):
        payload[f"filtro_{filtro_numero}"] = "1.2" if filtro_numero in alarm_filters else "0.8"
    return payload


def _build_temperatura_payload(
    submit_action: str,
    *,
    data_referencia: str = "2026-04-13",
    responsavel_nome: str = "Operador Forno ED",
    observacoes_gerais: str = "Leitura térmica",
    outlier_zones: set[int] | None = None,
) -> dict[str, str]:
    outlier_zones = outlier_zones or set()
    payload: dict[str, str] = {
        "data_referencia": data_referencia,
        "responsavel_nome": responsavel_nome,
        "observacoes_gerais": observacoes_gerais,
        "submit_action": submit_action,
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
    outliers = {
        1: "150",
        2: "150",
        3: "180",
        4: "210",
        5: "190",
        6: "210",
        7: "210",
        8: "210",
        9: "210",
        10: "210",
        11: "210",
        12: "210",
    }
    for zona_numero in range(1, 13):
        payload[f"zona_{zona_numero}"] = outliers[zona_numero] if zona_numero in outlier_zones else defaults[zona_numero]
    return payload


def _build_tensao_payload(
    turno: str,
    modelo: str,
    submit_action: str,
    *,
    data_referencia: str = "2026-04-13",
    responsavel_nome: str = "Condutor PT/ED",
    observacoes_gerais: str = "Leitura de retificadores",
    outlier_zones: set[int] | None = None,
) -> dict[str, str]:
    outlier_zones = outlier_zones or set()
    payload: dict[str, str] = {
        "data_referencia": data_referencia,
        "turno": turno,
        "modelo": modelo,
        "responsavel_nome": responsavel_nome,
        "observacoes_gerais": observacoes_gerais,
        "submit_action": submit_action,
    }
    for zona_numero in range(1, 30):
        payload[f"zona_{zona_numero}"] = "420" if zona_numero in outlier_zones else "220"
    return payload


def test_dashboard_page_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Dashboard Operacional do Dia" in response.text
    assert "Alertas do dia" in response.text
    assert "Não iniciado" in response.text


def test_dashboard_without_data_shows_safe_state(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    response = client.get("/dashboard?data_referencia=2026-04-13")

    assert response.status_code == 200
    assert "Operação do dia sem desvios ativos até o momento" in response.text
    assert "Sem problemas no dia" in response.text


def test_dashboard_shows_operational_summary(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env

    ed_payload = _build_form_payload(session_factory, "Laboratório", "1", "rascunho")
    item_ids = ed_payload["item_ids"]
    assert isinstance(item_ids, list)
    first_item_id = item_ids[0]
    ed_payload[f"valor_{first_item_id}"] = "30"
    ed_payload[f"observacao_{first_item_id}"] = "Acima do padrão"
    client.post("/ed/salvar", data=ed_payload)

    client.post("/ed/salvar", data=_build_form_payload(session_factory, "PT/ED", "2", "concluido"))
    client.post(
        "/pressao-filtros-ed/salvar",
        data=_build_pressao_payload("1", "rascunho", alarm_filters={2}, responsavel_nome="Condutor turno 1"),
    )
    client.post(
        "/pressao-filtros-ed/salvar",
        data=_build_pressao_payload("2", "concluido", responsavel_nome="Condutor turno 2"),
    )
    client.post(
        "/temperatura-forno-ed/salvar",
        data=_build_temperatura_payload("concluido", outlier_zones={4, 5}, responsavel_nome="Operador forno"),
    )
    client.post(
        "/tensao-retificadores-ed/salvar",
        data=_build_tensao_payload("1", "HB20", "rascunho", outlier_zones={3, 8}, responsavel_nome="Líder retificador"),
    )

    response = client.get("/dashboard?data_referencia=2026-04-13")

    assert response.status_code == 200
    assert "Atenção: existem desvios no processo hoje" in response.text
    assert "Total de alertas" in response.text
    assert "filtro em alarme" in response.text or "filtros em alarme" in response.text
    assert "zona fora do padrão" in response.text or "zonas fora do padrão" in response.text
    assert "item(ns) fora do padrão" in response.text
    assert "Tensão dos Retificadores ED" in response.text
    assert "Turno 1" in response.text
    assert "Turno 2" in response.text
    assert "Crítico" in response.text


def test_dashboard_snapshot_calculates_priorities_and_alerts(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    client.post(
        "/pressao-filtros-ed/salvar",
        data=_build_pressao_payload("1", "rascunho"),
    )
    client.post(
        "/tensao-retificadores-ed/salvar",
        data=_build_tensao_payload("1", "Onix", "concluido", outlier_zones={1, 2}),
    )
    client.post(
        "/temperatura-forno-ed/salvar",
        data=_build_temperatura_payload("concluido", outlier_zones={1}),
    )

    with session_factory() as session:
        filters = parse_dashboard_filters({"data_referencia": "2026-04-13"}, session)
        snapshot = build_dashboard_snapshot(session, filters)

    assert snapshot.has_global_alert is True
    assert snapshot.global_alert_message == "Atenção: existem desvios no processo hoje"
    assert len(snapshot.alert_summaries) == 4
    assert any(card.title == "ED" and card.priority_label == "Não iniciado" for card in snapshot.module_cards)
    assert any(card.title == "Pressão dos Filtros ED" and card.priority_label == "Atenção" for card in snapshot.module_cards)
    assert any(card.title == "Tensão dos Retificadores ED" and card.priority_label == "Crítico" for card in snapshot.module_cards)
    assert any(card.title == "Temperatura Forno ED" and card.priority_label == "Crítico" for card in snapshot.module_cards)
    assert any(metric.label == "Total de alertas" and metric.value == 3 for metric in snapshot.metrics)


def test_dashboard_filters_recent_launches_by_turno(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    client.post("/ed/salvar", data=_build_form_payload(session_factory, "Laboratório", "1", "rascunho"))
    client.post("/ed/salvar", data=_build_form_payload(session_factory, "PT/ED", "2", "concluido"))
    client.post(
        "/pressao-filtros-ed/salvar",
        data=_build_pressao_payload("2", "concluido", responsavel_nome="Operador turno 2"),
    )

    response = client.get("/dashboard?data_referencia=2026-04-13&turno=1")

    assert response.status_code == 200
    assert "Operador turno 2" not in response.text
    assert "Sem problemas no dia" in response.text


def test_dashboard_shows_continue_action_for_draft(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    client.post("/pressao-filtros-ed/salvar", data=_build_pressao_payload("1", "rascunho"))

    response = client.get("/dashboard?data_referencia=2026-04-13&turno=1")

    assert response.status_code == 200
    assert "Continuar" in response.text
    assert "Atenção" in response.text


def test_tensao_retificadores_page_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    response = client.get("/tensao-retificadores-ed")

    assert response.status_code == 200
    assert "Tensão dos Retificadores ED" in response.text
    assert "Carregar formulário" in response.text


def test_tensao_retificadores_load_form(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    response = client.post(
        "/tensao-retificadores-ed/carregar",
        data={
            "data_referencia": "2026-04-13",
            "turno": "1",
            "modelo": "HB20",
            "responsavel_nome": "Condutor PT/ED",
            "observacoes_gerais": "",
        },
    )

    assert response.status_code == 200
    assert "Zona 29" in response.text
    assert "80V a 400V" in response.text


def test_tensao_retificadores_create_draft(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_tensao_payload("1", "HB20", "rascunho")

    response = client.post("/tensao-retificadores-ed/salvar", data=payload)

    assert response.status_code == 200
    assert "Rascunho" in response.text
    assert "Continuar edição" in response.text

    with session_factory() as session:
        lancamento = session.scalars(select(TensaoRetificadoresLancamento)).first()
        assert lancamento is not None
        assert lancamento.status == "rascunho"
        assert lancamento.modelo == "HB20"
        assert lancamento.total_zonas_fora_padrao == 0


def test_tensao_retificadores_complete_launch(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_tensao_payload("2", "Onix", "concluido")

    response = client.post("/tensao-retificadores-ed/salvar", data=payload)

    assert response.status_code == 200
    assert "Concluído" in response.text
    assert "Continuar edição" not in response.text

    with session_factory() as session:
        lancamento = session.scalars(select(TensaoRetificadoresLancamento)).first()
        assert lancamento is not None
        assert lancamento.status == "concluido"


def test_tensao_retificadores_marks_outlier_zones(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_tensao_payload("1", "Argo", "rascunho", outlier_zones={2, 7, 11})

    response = client.post("/tensao-retificadores-ed/salvar", data=payload)

    assert response.status_code == 200
    assert "Fora do padrão" in response.text

    with session_factory() as session:
        lancamento = session.scalars(select(TensaoRetificadoresLancamento)).first()
        assert lancamento is not None
        assert lancamento.total_zonas_fora_padrao == 3


def test_tensao_retificadores_allows_multiple_models_same_day(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    client.post("/tensao-retificadores-ed/salvar", data=_build_tensao_payload("1", "HB20", "rascunho"))
    client.post("/tensao-retificadores-ed/salvar", data=_build_tensao_payload("1", "Onix", "rascunho"))

    with session_factory() as session:
        lancamentos = session.scalars(select(TensaoRetificadoresLancamento).order_by(TensaoRetificadoresLancamento.modelo)).all()

    assert len(lancamentos) == 2
    assert [lancamento.modelo for lancamento in lancamentos] == ["HB20", "Onix"]


def test_tensao_retificadores_blocks_duplicate_context(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    payload = _build_tensao_payload("1", "HB20", "rascunho")
    client.post("/tensao-retificadores-ed/salvar", data=payload)

    response = client.post("/tensao-retificadores-ed/salvar", data=payload)

    assert response.status_code == 400
    assert "Já existe lançamento para este contexto" in response.text


def test_tensao_retificadores_history_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    client.post(
        "/tensao-retificadores-ed/salvar",
        data=_build_tensao_payload("1", "HB20", "rascunho", outlier_zones={4}),
    )

    response = client.get("/tensao-retificadores-ed/historico?somente_fora_padrao=true")

    assert response.status_code == 200
    assert "Histórico · Tensão dos Retificadores ED" in response.text
    assert "HB20" in response.text


def test_tensao_retificadores_detail_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    client.post(
        "/tensao-retificadores-ed/salvar",
        data=_build_tensao_payload("3", "Argo", "rascunho", observacoes_gerais="Detalhe retificador"),
    )

    with session_factory() as session:
        lancamento = session.scalars(select(TensaoRetificadoresLancamento)).first()
        assert lancamento is not None
        lancamento_id = lancamento.id

    response = client.get(f"/tensao-retificadores-ed/lancamentos/{lancamento_id}")

    assert response.status_code == 200
    assert "Detalhe retificador" in response.text
    assert "Zona 29" in response.text


def test_tensao_retificadores_completed_launch_cannot_be_edited(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    client.post("/tensao-retificadores-ed/salvar", data=_build_tensao_payload("2", "Kwid", "concluido"))

    with session_factory() as session:
        lancamento = session.scalars(select(TensaoRetificadoresLancamento)).first()
        assert lancamento is not None
        lancamento_id = lancamento.id

    response = client.get(f"/tensao-retificadores-ed/lancamentos/{lancamento_id}/editar")

    assert response.status_code == 200
    assert "Visualização consolidada do lançamento" in response.text
    assert "Salvar rascunho" not in response.text


def test_ed_page_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    response = client.get("/ed")
    assert response.status_code == 200
    assert "Carregar itens" in response.text
    assert "Fluxo operacional" in response.text


def test_ed_load_shows_progress_and_context_status(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_form_payload(session_factory, "Laboratório", "1", "rascunho")
    client.post("/ed/salvar", data=payload)

    response = client.post(
        "/ed/carregar",
        data={
            "data_referencia": "2026-04-13",
            "tipo_dia": "normal",
            "setor": "Laboratório",
            "turno": "1",
            "responsavel_nome": "Laboratório",
            "observacoes_gerais": "",
        },
    )

    assert response.status_code == 200
    assert "Já existe lançamento para este contexto" in response.text
    assert "Continuar edição" in response.text
    assert "0 /" in response.text or "itens preenchidos" in response.text


def test_create_ed_draft(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_form_payload(session_factory, "Laboratório", "1", "rascunho")

    response = client.post("/ed/salvar", data=payload)

    assert response.status_code == 200
    assert "Rascunho" in response.text
    assert "Continuar edição" in response.text

    with session_factory() as session:
        lancamento = session.scalars(select(EDLancamento)).first()
        assert lancamento is not None
        assert lancamento.status == "rascunho"
        assert lancamento.setor == "Laboratório"


def test_complete_ed_launch(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_form_payload(session_factory, "PT/ED", "1", "concluido")

    response = client.post("/ed/salvar", data=payload)

    assert response.status_code == 200
    assert "Concluído" in response.text
    assert "Continuar edição" not in response.text

    with session_factory() as session:
        lancamento = session.scalars(select(EDLancamento)).first()
        assert lancamento is not None
        assert lancamento.status == "concluido"


def test_ed_history_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_form_payload(session_factory, "Laboratório", "1", "rascunho")
    client.post("/ed/salvar", data=payload)

    response = client.get("/ed/historico")

    assert response.status_code == 200
    assert "Histórico da ED" in response.text
    assert "Laboratório" in response.text


def test_ed_requires_observation_when_out_of_parameter(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_form_payload(session_factory, "Laboratório", "1", "rascunho")

    item_ids = payload["item_ids"]
    assert isinstance(item_ids, list)
    first_item_id = item_ids[0]
    payload[f"valor_{first_item_id}"] = "30"
    payload[f"observacao_{first_item_id}"] = ""

    response = client.post("/ed/salvar", data=payload)

    assert response.status_code == 400
    assert "Informe observação para itens fora do padrão" in response.text


def test_ed_history_filters_by_date_range(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload_old = _build_form_payload(
        session_factory,
        "Laboratório",
        "1",
        "rascunho",
        data_referencia="2026-04-10",
        observacoes_gerais="Lançamento antigo",
    )
    payload_new = _build_form_payload(
        session_factory,
        "PT/ED",
        "1",
        "rascunho",
        data_referencia="2026-04-13",
        observacoes_gerais="Lançamento recente",
    )
    client.post("/ed/salvar", data=payload_old)
    client.post("/ed/salvar", data=payload_new)

    response = client.get("/ed/historico?data_inicial=2026-04-12&data_final=2026-04-13")

    assert response.status_code == 200
    assert "13/04/2026" in response.text
    assert "10/04/2026" not in response.text


def test_ed_detail_page_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_form_payload(session_factory, "Laboratório", "1", "rascunho")
    client.post("/ed/salvar", data=payload)

    with session_factory() as session:
        lancamento = session.scalars(select(EDLancamento)).first()
        assert lancamento is not None
        lancamento_id = lancamento.id

    response = client.get(f"/ed/lancamentos/{lancamento_id}")

    assert response.status_code == 200
    assert "Detalhe do lançamento" in response.text
    assert "Lançamento de teste" in response.text


def test_completed_launch_cannot_be_edited(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_form_payload(session_factory, "PT/ED", "1", "concluido")
    client.post("/ed/salvar", data=payload)

    with session_factory() as session:
        lancamento = session.scalars(select(EDLancamento)).first()
        assert lancamento is not None
        lancamento_id = lancamento.id

    response = client.get(f"/ed/lancamentos/{lancamento_id}/editar")

    assert response.status_code == 200
    assert "Detalhe do lançamento" in response.text
    assert "Salvar rascunho" not in response.text


def test_cadastros_route_keeps_precedence(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    response = client.get("/cadastros")
    assert response.status_code == 200
    assert "Cadastros fixos" in response.text


def test_pressao_filtros_page_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    response = client.get("/pressao-filtros-ed")
    assert response.status_code == 200
    assert "Pressão dos Filtros ED" in response.text
    assert "Carregar formulário" in response.text


def test_pressao_filtros_load_form(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    response = client.post(
        "/pressao-filtros-ed/carregar",
        data={
            "data_referencia": "2026-04-13",
            "turno": "1",
            "responsavel_nome": "Condutor PT/ED",
            "observacoes_gerais": "",
        },
    )
    assert response.status_code == 200
    assert "Filtro 24" in response.text
    assert "24" in response.text


def test_pressao_filtros_create_draft(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_pressao_payload("1", "rascunho")
    response = client.post("/pressao-filtros-ed/salvar", data=payload)

    assert response.status_code == 200
    assert "Rascunho" in response.text
    assert "Continuar edição" in response.text

    with session_factory() as session:
        lancamento = session.scalars(select(PressaoFiltrosLancamento)).first()
        assert lancamento is not None
        assert lancamento.status == "rascunho"


def test_pressao_filtros_complete_launch(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_pressao_payload("2", "concluido")
    response = client.post("/pressao-filtros-ed/salvar", data=payload)

    assert response.status_code == 200
    assert "Concluído" in response.text
    assert "Continuar edição" not in response.text

    with session_factory() as session:
        lancamento = session.scalars(select(PressaoFiltrosLancamento)).first()
        assert lancamento is not None
        assert lancamento.status == "concluido"


def test_pressao_filtros_alarm_is_calculated(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_pressao_payload("1", "rascunho", alarm_filters={2, 7})
    response = client.post("/pressao-filtros-ed/salvar", data=payload)

    assert response.status_code == 200
    assert "Em alarme" in response.text

    with session_factory() as session:
        lancamento = session.scalars(select(PressaoFiltrosLancamento)).first()
        assert lancamento is not None
        assert lancamento.total_filtros_em_alarme == 2


def test_pressao_filtros_history_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    payload = _build_pressao_payload("1", "rascunho", alarm_filters={5})
    client.post("/pressao-filtros-ed/salvar", data=payload)

    response = client.get("/pressao-filtros-ed/historico?somente_alarme=true")

    assert response.status_code == 200
    assert "Histórico · Pressão dos Filtros ED" in response.text
    assert "Em alarme" in response.text or ">0<" not in response.text


def test_pressao_filtros_detail_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_pressao_payload("1", "rascunho", observacoes_gerais="Detalhe pressão")
    client.post("/pressao-filtros-ed/salvar", data=payload)

    with session_factory() as session:
        lancamento = session.scalars(select(PressaoFiltrosLancamento)).first()
        assert lancamento is not None
        lancamento_id = lancamento.id

    response = client.get(f"/pressao-filtros-ed/lancamentos/{lancamento_id}")

    assert response.status_code == 200
    assert "Detalhe pressão" in response.text
    assert "Filtro 24" in response.text


def test_pressao_filtros_completed_launch_cannot_be_edited(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_pressao_payload("3", "concluido")
    client.post("/pressao-filtros-ed/salvar", data=payload)

    with session_factory() as session:
        lancamento = session.scalars(select(PressaoFiltrosLancamento)).first()
        assert lancamento is not None
        lancamento_id = lancamento.id

    response = client.get(f"/pressao-filtros-ed/lancamentos/{lancamento_id}/editar")

    assert response.status_code == 200
    assert "Visualização consolidada do lançamento" in response.text
    assert "Salvar rascunho" not in response.text


def test_temperatura_forno_page_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    response = client.get("/temperatura-forno-ed")
    assert response.status_code == 200
    assert "Temperatura Forno ED" in response.text
    assert "Carregar formulário" in response.text


def test_temperatura_forno_load_form(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    response = client.post(
        "/temperatura-forno-ed/carregar",
        data={
            "data_referencia": "2026-04-13",
            "responsavel_nome": "Operador Forno ED",
            "observacoes_gerais": "",
        },
    )
    assert response.status_code == 200
    assert "Zona 12" in response.text
    assert "Faixa esperada" in response.text


def test_temperatura_forno_create_draft(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_temperatura_payload("rascunho")
    response = client.post("/temperatura-forno-ed/salvar", data=payload)

    assert response.status_code == 200
    assert "Rascunho" in response.text
    assert "Continuar edição" in response.text

    with session_factory() as session:
        lancamento = session.scalars(select(TemperaturaFornoLancamento)).first()
        assert lancamento is not None
        assert lancamento.status == "rascunho"
        assert lancamento.total_zonas_fora_padrao == 0


def test_temperatura_forno_complete_launch(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_temperatura_payload("concluido")
    response = client.post("/temperatura-forno-ed/salvar", data=payload)

    assert response.status_code == 200
    assert "Concluído" in response.text
    assert "Continuar edição" not in response.text

    with session_factory() as session:
        lancamento = session.scalars(select(TemperaturaFornoLancamento)).first()
        assert lancamento is not None
        assert lancamento.status == "concluido"


def test_temperatura_forno_marks_zone_inside_range(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    payload = _build_temperatura_payload("rascunho")
    response = client.post("/temperatura-forno-ed/salvar", data=payload)

    assert response.status_code == 200
    assert "Dentro da faixa" in response.text


def test_temperatura_forno_marks_zone_out_of_range(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_temperatura_payload("rascunho", outlier_zones={1, 4})
    response = client.post("/temperatura-forno-ed/salvar", data=payload)

    assert response.status_code == 200
    assert "Fora do padrão" in response.text

    with session_factory() as session:
        lancamento = session.scalars(select(TemperaturaFornoLancamento)).first()
        assert lancamento is not None
        assert lancamento.total_zonas_fora_padrao == 2


def test_temperatura_forno_history_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    payload = _build_temperatura_payload("rascunho", outlier_zones={3})
    client.post("/temperatura-forno-ed/salvar", data=payload)

    response = client.get("/temperatura-forno-ed/historico?somente_fora_padrao=true")

    assert response.status_code == 200
    assert "Histórico · Temperatura Forno ED" in response.text
    assert "Operador Forno ED" in response.text


def test_temperatura_forno_detail_loads(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_temperatura_payload("rascunho", observacoes_gerais="Detalhe térmico")
    client.post("/temperatura-forno-ed/salvar", data=payload)

    with session_factory() as session:
        lancamento = session.scalars(select(TemperaturaFornoLancamento)).first()
        assert lancamento is not None
        lancamento_id = lancamento.id

    response = client.get(f"/temperatura-forno-ed/lancamentos/{lancamento_id}")

    assert response.status_code == 200
    assert "Detalhe térmico" in response.text
    assert "Zona 12" in response.text


def test_temperatura_forno_completed_launch_cannot_be_edited(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    payload = _build_temperatura_payload("concluido")
    client.post("/temperatura-forno-ed/salvar", data=payload)

    with session_factory() as session:
        lancamento = session.scalars(select(TemperaturaFornoLancamento)).first()
        assert lancamento is not None
        lancamento_id = lancamento.id

    response = client.get(f"/temperatura-forno-ed/lancamentos/{lancamento_id}/editar")

    assert response.status_code == 200
    assert "Visualização consolidada do lançamento" in response.text
    assert "Salvar rascunho" not in response.text
