from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BeneficioDetalhado(BaseModel):
    nome: str = Field(..., description="Nome do benefício (ex: Auxílio Brasil)")
    situacao: Optional[str] = None
    valor_ultima_parcela: Optional[float] = None
    data_ultima_parcela: Optional[str] = None
    total_recebido: Optional[float] = None
    periodo_inicio: Optional[str] = None
    periodo_fim: Optional[str] = None


class ConsultaRequest(BaseModel):
    nome: Optional[str] = Field(None, description="Nome completo da pessoa")
    cpf: Optional[str] = Field(None, description="CPF (11 dígitos) ou NIS")
    filtro: Optional[str] = Field(
        None, description='Filtro opcional: "BENEFICIÁRIO DE PROGRAMA SOCIAL"'
    )


class ResultadoSucesso(BaseModel):
    status: str = "sucesso"
    identificador: str = Field(..., description="Identificador único da consulta")
    nome: Optional[str] = None
    cpf: Optional[str] = None
    data_nascimento: Optional[str] = None
    beneficios: list[BeneficioDetalhado] = []
    screenshot_base64: Optional[str] = None
    data_consulta: str = Field(default_factory=lambda: datetime.now().isoformat())


class ResultadoErro(BaseModel):
    status: str = "erro"
    identificador: str = Field(..., description="Identificador único da consulta")
    mensagem: str = Field(..., description="Mensagem de erro descritiva")
    data_consulta: str = Field(default_factory=lambda: datetime.now().isoformat())


class ResultadoConsulta(BaseModel):
    resultado: ResultadoSucesso | ResultadoErro