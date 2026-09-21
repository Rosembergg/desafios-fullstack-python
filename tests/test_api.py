"""Testes da API /consulta cobrindo os 5 cenários do desafio.

As funções de automação (Playwright) são mockadas: o objetivo aqui é validar
o contrato da API e as regras de negócio (mensagens de erro, montagem do
resultado), não repetir o teste de scraping em si — esse já foi validado
manualmente contra o Portal da Transparência real (ver README).
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.server import app

client = TestClient(app)


def _mock_context():
    context = AsyncMock()
    context.close = AsyncMock()
    return context


@pytest.fixture(autouse=True)
def mock_navegador():
    with patch("src.api.server.GerenciadorNavegador.criar_contexto", new=AsyncMock(return_value=_mock_context())):
        yield


def test_sem_nome_e_sem_cpf_retorna_400():
    resposta = client.post("/consulta", json={})
    assert resposta.status_code == 400
    assert "obrigat" in resposta.json()["detail"].lower()


@patch("src.api.server.capturar_evidencia_base64", new=AsyncMock(return_value="ZmFrZV9wbmc="))
@patch("src.api.server.extrair_beneficios", new=AsyncMock(return_value=[
    {"nome": "Auxílio Emergencial", "situacao": "Regular", "valor_ultima_parcela": 300.0,
     "data_ultima_parcela": "01/2021", "total_recebido": 3300.0, "periodo_inicio": "04/2020", "periodo_fim": "01/2021"},
]))
@patch("src.api.server.extrair_panorama", new=AsyncMock(return_value={"nome": "FULANO DE TAL", "cpf": "***.123.456-**"}))
@patch("src.api.server.acessar_primeiro_resultado", new=AsyncMock(return_value=True))
@patch("src.api.server.obter_quantidade_resultados", new=AsyncMock(return_value=1))
@patch("src.api.server.aguardar_resultados", new=AsyncMock())
@patch("src.api.server.realizar_busca", new=AsyncMock())
@patch("src.api.server.navegar_para_busca", new=AsyncMock(return_value=AsyncMock(close=AsyncMock())))
def test_sucesso_por_cpf():
    resposta = client.post("/consulta", json={"cpf": "12345678900"})
    assert resposta.status_code == 200
    resultado = resposta.json()["resultado"]
    assert resultado["status"] == "sucesso"
    assert resultado["nome"] == "FULANO DE TAL"
    assert len(resultado["beneficios"]) == 1
    assert resultado["beneficios"][0]["nome"] == "Auxílio Emergencial"
    assert resultado["screenshot_base64"] == "ZmFrZV9wbmc="


@patch("src.api.server.extrair_panorama", new=AsyncMock(return_value={"nome": "FULANA DE TAL", "cpf": None}))
@patch("src.api.server.extrair_beneficios", new=AsyncMock(return_value=[]))
@patch("src.api.server.capturar_evidencia_base64", new=AsyncMock(return_value="ZmFrZV9wbmc="))
@patch("src.api.server.acessar_primeiro_resultado", new=AsyncMock(return_value=True))
@patch("src.api.server.obter_quantidade_resultados", new=AsyncMock(return_value=1))
@patch("src.api.server.aguardar_resultados", new=AsyncMock())
@patch("src.api.server.realizar_busca", new=AsyncMock())
@patch("src.api.server.navegar_para_busca", new=AsyncMock(return_value=AsyncMock(close=AsyncMock())))
def test_sucesso_por_nome():
    resposta = client.post("/consulta", json={"nome": "Fulana de Tal"})
    assert resposta.status_code == 200
    resultado = resposta.json()["resultado"]
    assert resultado["status"] == "sucesso"
    assert resultado["nome"] == "FULANA DE TAL"


@patch("src.api.server.obter_quantidade_resultados", new=AsyncMock(return_value=0))
@patch("src.api.server.aguardar_resultados", new=AsyncMock())
@patch("src.api.server.realizar_busca", new=AsyncMock())
@patch("src.api.server.navegar_para_busca", new=AsyncMock(return_value=AsyncMock(close=AsyncMock())))
def test_erro_cpf_inexistente():
    resposta = client.post("/consulta", json={"cpf": "00000000000"})
    assert resposta.status_code == 200
    resultado = resposta.json()["resultado"]
    assert resultado["status"] == "erro"
    assert resultado["mensagem"] == "Não foi possível retornar os dados no tempo de resposta solicitado."


@patch("src.api.server.obter_quantidade_resultados", new=AsyncMock(return_value=0))
@patch("src.api.server.aguardar_resultados", new=AsyncMock())
@patch("src.api.server.realizar_busca", new=AsyncMock())
@patch("src.api.server.navegar_para_busca", new=AsyncMock(return_value=AsyncMock(close=AsyncMock())))
def test_erro_nome_inexistente():
    resposta = client.post("/consulta", json={"nome": "Nome Que Nao Existe De Jeito Nenhum"})
    assert resposta.status_code == 200
    resultado = resposta.json()["resultado"]
    assert resultado["status"] == "erro"
    assert "0 resultados" in resultado["mensagem"]


@patch("src.api.server.extrair_panorama", new=AsyncMock(return_value={"nome": "BENEFICIARIO SOCIAL", "cpf": None}))
@patch("src.api.server.extrair_beneficios", new=AsyncMock(return_value=[]))
@patch("src.api.server.capturar_evidencia_base64", new=AsyncMock(return_value=None))
@patch("src.api.server.acessar_primeiro_resultado", new=AsyncMock(return_value=True))
@patch("src.api.server.obter_quantidade_resultados", new=AsyncMock(return_value=1))
@patch("src.api.server.aguardar_resultados", new=AsyncMock())
@patch("src.api.server.realizar_busca", new=AsyncMock())
@patch("src.api.server.navegar_para_busca", new=AsyncMock(return_value=AsyncMock(close=AsyncMock())))
def test_busca_filtrada_por_beneficio_social():
    resposta = client.post(
        "/consulta",
        json={"nome": "Silva", "filtro": "BENEFICIÁRIO DE PROGRAMA SOCIAL"},
    )
    assert resposta.status_code == 200
    assert resposta.json()["resultado"]["status"] == "sucesso"
