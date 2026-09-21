import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException

from src.bot.navegador import GerenciadorNavegador
from src.bot.busca import (
    navegar_para_busca,
    realizar_busca,
    aguardar_resultados,
    obter_quantidade_resultados,
    acessar_primeiro_resultado,
    extrair_panorama,
    extrair_beneficios,
    capturar_evidencia_base64,
)
from src.schemas.models import (
    ConsultaRequest,
    ResultadoSucesso,
    ResultadoErro,
    ResultadoConsulta,
    BeneficioDetalhado,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await GerenciadorNavegador.fechar()


app = FastAPI(
    title="Robô Consulta Portal da Transparência",
    description=(
        "API que automatiza a consulta de pessoas físicas no Portal da Transparência "
        "(RPA com Playwright), retornando um panorama da relação da pessoa com o "
        "Governo Federal, benefícios sociais recebidos e uma evidência da consulta em Base64."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


def _salvar_resultado(identificador: str, payload: dict) -> None:
    """Persiste o JSON da consulta em output/, no formato usado pela Parte 2 (Hiperautomação)."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = OUTPUT_DIR / f"{identificador}_{timestamp}.json"
    caminho.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@app.post("/consulta", response_model=ResultadoConsulta)
async def consultar(request: ConsultaRequest):
    if not request.nome and not request.cpf:
        raise HTTPException(
            status_code=400,
            detail="É obrigatório informar 'nome' ou 'cpf' para realizar a consulta.",
        )

    identificador = str(uuid.uuid4())
    termo = request.nome or request.cpf or ""
    logger.info("Consulta %s iniciada — termo: %s", identificador, termo)

    context = await GerenciadorNavegador.criar_contexto()
    page = None
    try:
        page = await navegar_para_busca(context)
        await realizar_busca(page, termo, request.filtro)
        await aguardar_resultados(page)

        quantidade = await obter_quantidade_resultados(page)
        if quantidade == 0:
            if request.cpf:
                mensagem = "Não foi possível retornar os dados no tempo de resposta solicitado."
            else:
                mensagem = f"Foram encontrados 0 resultados para o termo {termo!r}."
            logger.warning("Consulta %s: %s", identificador, mensagem)
            resultado = ResultadoErro(identificador=identificador, mensagem=mensagem)
            _salvar_resultado(identificador, resultado.model_dump())
            return ResultadoConsulta(resultado=resultado)

        encontrou = await acessar_primeiro_resultado(page)
        if not encontrou:
            resultado = ResultadoErro(
                identificador=identificador,
                mensagem="Não foi possível acessar os detalhes do resultado encontrado.",
            )
            _salvar_resultado(identificador, resultado.model_dump())
            return ResultadoConsulta(resultado=resultado)

        panorama = await extrair_panorama(page)
        beneficios_dados = await extrair_beneficios(page)
        evidencia = await capturar_evidencia_base64(page)

        resultado = ResultadoSucesso(
            identificador=identificador,
            nome=panorama.get("nome"),
            cpf=panorama.get("cpf") or request.cpf,
            beneficios=[BeneficioDetalhado(**b) for b in beneficios_dados],
            screenshot_base64=evidencia,
        )
        logger.info("Consulta %s concluída com sucesso.", identificador)
        _salvar_resultado(identificador, resultado.model_dump())
        return ResultadoConsulta(resultado=resultado)

    except Exception as exc:
        logger.error("Consulta %s: erro inesperado — %s", identificador, exc, exc_info=True)
        resultado = ResultadoErro(
            identificador=identificador,
            mensagem=f"Não foi possível retornar os dados no tempo de resposta solicitado. Erro: {str(exc)}",
        )
        _salvar_resultado(identificador, resultado.model_dump())
        return ResultadoConsulta(resultado=resultado)
    finally:
        if page:
            await page.close()
        await context.close()
