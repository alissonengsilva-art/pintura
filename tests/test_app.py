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
from app.models import Base, ItemED, Modelo, OperationalModuleRecord, Responsavel, Setor, TemperaturaFornoLancamento, Turno
from app.services.ed_seed_data import DEFAULT_RESPONSAVEIS, DEFAULT_SETORES, DEFAULT_TURNOS, build_seed_items
from app.services.operational_module_service import (
    MODULE_STATUS_CONCLUIDO,
    MODULE_STATUS_EM_ANDAMENTO,
    MODULE_STATUS_PARCIAL,
)


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
        session.add(Modelo(nome="HB20", codigo="HB20", ativo=True))
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


def _base_sector_payload(**extra: str) -> dict[str, str]:
    payload = {
        "data_referencia": "2026-04-16",
        "responsavel_nome_PTED": "Condutor PT/ED",
        "observacoes_setor_PTED": "PTED ok",
        "responsavel_nome_LABORATORIO": "Laboratório",
        "observacoes_setor_LABORATORIO": "Lab ok",
    }
    payload.update(extra)
    return payload


def _ed_payload(setor: str) -> dict[str, str]:
    payload = _base_sector_payload(tipo_dia="normal", turno="1")
    payload.update({f"value_{setor}_1": "20", f"obs_{setor}_1": "ok"})
    return payload


def _temperatura_payload(setor: str, outlier: bool = False) -> dict[str, str]:
    payload = _base_sector_payload()
    defaults = {1: "90", 2: "90", 3: "130", 4: "170", 5: "160", 6: "180", 7: "180", 8: "180", 9: "180", 10: "180", 11: "180", 12: "180"}
    for zona, value in defaults.items():
        payload[f"value_{setor}_{zona}"] = "210" if outlier and zona == 4 else value
    return payload


def _pressao_payload(setor: str, alarmes: set[int] | None = None) -> dict[str, str]:
    payload = _base_sector_payload(turno="1")
    alarmes = alarmes or set()
    for filtro in range(1, 25):
        payload[f"value_{setor}_{filtro}"] = "1.2" if filtro in alarmes else "0.8"
    return payload


def _tensao_payload(setor: str, outlier: bool = False) -> dict[str, str]:
    payload = _base_sector_payload(turno="1", modelo="HB20")
    for zona in range(1, 30):
        payload[f"value_{setor}_{zona}"] = "420" if outlier and zona == 2 else "220"
    return payload


def _poder_payload(setor: str) -> dict[str, str]:
    payload = _base_sector_payload(semana_referencia="2026-S16", modelo="HB20", cis="CIS-1", velocidade="2.5", tipo="Ensaio")
    for ponto in range(1, 31):
        payload[f"value_{setor}_{ponto}"] = "8.0" if ponto <= 3 else ""
    return payload


def _espessura_payload(setor: str) -> dict[str, str]:
    payload = _base_sector_payload(turno="1", modelo="HB20", cis="CIS-ESP")
    for ponto in range(1, 39):
        payload[f"value_{setor}_{ponto}"] = "25" if ponto <= 4 else ""
    return payload


def _rugosidade_payload(setor: str) -> dict[str, str]:
    payload = _base_sector_payload(sequencia="1ª coleta")
    for modelo in ["521", "226", "551", "598", "291"]:
        payload[f"value_{setor}_{modelo}"] = "12"
    return payload


def _aspecto_payload(setor: str) -> dict[str, str]:
    payload = _base_sector_payload(turno="1", modelo="HB20")
    payload.update(
        {
            f"cis_{setor}_1": "CIS-900",
            f"cod_posicao_{setor}_1": "P-1",
            f"local_{setor}_1": "Capo",
            f"anomalia_{setor}_1": "Cratera",
            f"lado_{setor}_1": "LE",
            f"geracao_{setor}_1": "G1",
            f"quantidade_{setor}_1": "2",
        }
    )
    return payload


@pytest.mark.parametrize(
    ("slug", "expected_text"),
    [
        ("/ed", "PTED"),
        ("/temperatura-forno-ed", "Laboratório"),
        ("/pressao-filtros-ed", "Filtro 24"),
        ("/tensao-retificadores-ed", "Zona 29"),
        ("/poder-penetracao", "Ponto 30"),
        ("/espessura-ed", "Ponto 38"),
        ("/aspecto", "Anomalia"),
        ("/rugosidade", "Modelo 291"),
    ],
)
def test_module_home_shows_direct_operational_form(
    test_env: tuple[TestClient, sessionmaker],
    slug: str,
    expected_text: str,
) -> None:
    client, _ = test_env
    response = client.get(slug)

    assert response.status_code == 200
    assert "Carregar formul" not in response.text
    assert "Carregar itens" not in response.text
    assert expected_text in response.text


def test_sector_saves_independently_and_general_status_becomes_partial(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env

    response = client.post("/pressao-filtros-ed/setores/PTED/salvar", data=_pressao_payload("PTED", {2}))

    assert response.status_code == 200
    assert "PTED" in response.text
    assert "Em andamento" in response.text

    with session_factory() as session:
        record = session.scalars(select(OperationalModuleRecord)).first()
        assert record is not None
        assert record.status_geral == MODULE_STATUS_EM_ANDAMENTO

    payload = {**_pressao_payload("LABORATORIO"), "submit_action": "concluir"}
    payload["responsavel_nome_LABORATORIO"] = "Analista Lab"
    response = client.post("/pressao-filtros-ed/setores/LABORATORIO/salvar", data=payload)

    assert response.status_code == 200

    with session_factory() as session:
        record = session.scalars(select(OperationalModuleRecord)).first()
        assert record is not None
        assert record.status_geral == MODULE_STATUS_PARCIAL


def test_module_becomes_concluded_when_both_sectors_finish(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env

    client.post("/temperatura-forno-ed/setores/PTED/salvar", data={**_temperatura_payload("PTED"), "submit_action": "concluir"})
    response = client.post("/temperatura-forno-ed/setores/LABORATORIO/salvar", data={**_temperatura_payload("LABORATORIO"), "submit_action": "concluir"})

    assert response.status_code == 200

    with session_factory() as session:
        record = session.scalars(select(OperationalModuleRecord)).first()
        assert record is not None
        assert record.status_geral == MODULE_STATUS_CONCLUIDO


def test_history_and_reports_show_consolidated_actions(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = test_env
    client.post("/espessura-ed/setores/PTED/salvar", data={**_espessura_payload("PTED"), "submit_action": "concluir"})
    client.post("/espessura-ed/setores/LABORATORIO/salvar", data={**_espessura_payload("LABORATORIO"), "submit_action": "concluir"})

    history = client.get("/espessura-ed/historico")
    assert history.status_code == 200
    assert "Consolidado" in history.text
    assert "Geral" in history.text
    assert "PTED" in history.text
    assert "Lab" in history.text

    with session_factory() as session:
        record = session.scalars(select(OperationalModuleRecord)).first()
        assert record is not None
        record_id = record.id

    detail = client.get(f"/espessura-ed/registros/{record_id}")
    report = client.get(f"/espessura-ed/registros/{record_id}/relatorio?setor=PTED")
    assert detail.status_code == 200
    assert report.status_code == 200
    assert "Visualização consolidada" in detail.text
    assert "Relatório" in report.text


def test_dashboard_reads_new_sector_model(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    client.post("/ed/setores/PTED/salvar", data={**_ed_payload("PTED"), "submit_action": "concluir"})
    client.post("/rugosidade/setores/LABORATORIO/salvar", data=_rugosidade_payload("LABORATORIO"))

    response = client.get("/dashboard?data_referencia=2026-04-16")

    assert response.status_code == 200
    assert "Dashboard por data" in response.text
    assert "PTED:" in response.text
    assert "Laboratorio:" in response.text
    assert "Iniciar" in response.text or "Continuar" in response.text


def test_legacy_history_remains_visible(test_env: tuple[TestClient, sessionmaker]) -> None:
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

    response = client.get("/temperatura-forno-ed/historico")
    legacy_detail = client.get(f"/temperatura-forno-ed/legado/{legacy_id}")

    assert response.status_code == 200
    assert "Legado" in response.text
    assert legacy_detail.status_code == 200
    assert "Registro antigo" in legacy_detail.text


def test_aspecto_supports_sector_specific_batch_rows(test_env: tuple[TestClient, sessionmaker]) -> None:
    client, _ = test_env
    response = client.post("/aspecto/setores/PTED/salvar", data={**_aspecto_payload("PTED"), "submit_action": "concluir"})

    assert response.status_code == 200
    assert "Cratera" in response.text
