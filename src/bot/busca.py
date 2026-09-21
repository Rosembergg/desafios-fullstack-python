import base64
import logging
import re
from typing import Optional

from playwright.async_api import BrowserContext, Page

logger = logging.getLogger(__name__)

URL_PORTAL = "https://portaldatransparencia.gov.br"
URL_HOME = f"{URL_PORTAL}/"
URL_BUSCA_PESSOA = f"{URL_PORTAL}/pessoa-fisica/busca/lista"

FILTROS_SUPORTADOS = {
    "BENEFICIÁRIO DE PROGRAMA SOCIAL": "beneficiarioProgramaSocial",
}

# O portal usa um desafio "Human Verification" (PerimeterX) para acessos que
# parecem automatizados. Visitar a home antes da página de busca, com um
# fingerprint de navegador comum, evita o bloqueio na prática.
STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = { runtime: {} };
"""


async def navegar_para_busca(context: BrowserContext) -> Page:
    """Abre o Portal da Transparência e navega até a busca de pessoas físicas."""
    page = await context.new_page()

    logger.info("Visitando a home do portal antes da busca (evita bloqueio anti-bot)...")
    await page.goto(URL_HOME, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1500)

    logger.info("Navegando para página de busca de pessoas físicas...")
    await page.goto(URL_BUSCA_PESSOA, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1500)

    await _aceitar_cookies(page)
    await page.wait_for_selector("#termo", state="visible", timeout=15000)
    logger.info("Página de busca carregada.")
    return page


async def _aceitar_cookies(page: Page) -> None:
    """Fecha o banner de cookies (LGPD) quando ele aparece."""
    try:
        botao = page.locator("#accept-all-btn")
        if await botao.is_visible(timeout=4000):
            await botao.click()
            await page.wait_for_timeout(300)
    except Exception:
        pass


async def realizar_busca(
    page: Page,
    termo: str,
    filtro_beneficio: Optional[str] = None,
) -> None:
    """Preenche o campo de busca com o termo e aplica o filtro opcional."""
    logger.info("Preenchendo campo de busca com: %s", termo)

    campo_busca = page.locator("#termo")
    await campo_busca.fill("")
    await campo_busca.fill(termo)

    id_checkbox = FILTROS_SUPORTADOS.get((filtro_beneficio or "").strip().upper())

    if id_checkbox:
        logger.info("Aplicando filtro: %s", filtro_beneficio)
        refine_header = page.locator('button[aria-controls="box-busca-refinada"]')
        await refine_header.click()
        checkbox = page.locator(f"#{id_checkbox}")
        await checkbox.wait_for(state="visible", timeout=5000)
        await checkbox.check(force=True)
        await page.locator("#btnConsultarPF").click()
    else:
        await page.locator(
            'form#form-superior button[aria-label="Enviar dados do formulário de busca"]'
        ).click()

    logger.info("Busca submetida.")


async def aguardar_resultados(page: Page) -> None:
    """Aguarda a página de resultados terminar de carregar."""
    await page.wait_for_selector("#countResultados", state="attached", timeout=20000)
    await page.wait_for_timeout(500)


async def obter_quantidade_resultados(page: Page) -> int:
    """Lê o total de resultados encontrados na busca."""
    texto = await page.locator("#countResultados").text_content()
    limpo = re.sub(r"[^\d]", "", texto or "0")
    try:
        return int(limpo or "0")
    except ValueError:
        return 0


async def acessar_primeiro_resultado(page: Page) -> bool:
    """Clica no link do primeiro resultado encontrado na lista."""
    try:
        primeiro_link = page.locator("a.link-busca-nome").first
        if await primeiro_link.is_visible(timeout=5000):
            await primeiro_link.click()
            await page.wait_for_load_state("domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1500)
            await _aceitar_cookies(page)
            return True
    except Exception:
        logger.warning("Nenhum resultado encontrado para clicar.", exc_info=True)
    return False


async def extrair_panorama(page: Page) -> dict:
    """Extrai nome, CPF e localidade da tela de Panorama da Pessoa Física."""
    dados: dict = {"nome": None, "cpf": None, "localidade": None}

    try:
        secao = page.locator("section.dados-tabelados")
        nome = await secao.locator("div:has(strong:text-is('Nome')) span").first.text_content()
        dados["nome"] = (nome or "").strip() or None
    except Exception:
        logger.warning("Não foi possível extrair o nome.", exc_info=True)

    try:
        cpf = await secao.locator("div:has(strong:text-is('CPF')) span").first.text_content()
        dados["cpf"] = (cpf or "").strip() or None
    except Exception:
        logger.warning("Não foi possível extrair o CPF.", exc_info=True)

    try:
        localidade = await secao.locator("div:has(strong:text-is('Localidade')) span").first.text_content()
        dados["localidade"] = (localidade or "").strip() or None
    except Exception:
        pass

    return dados


async def capturar_evidencia_base64(page: Page) -> Optional[str]:
    """Captura um screenshot da tela atual e retorna em Base64."""
    try:
        screenshot_bytes = await page.screenshot(full_page=True)
        return base64.b64encode(screenshot_bytes).decode("ascii")
    except Exception:
        logger.warning("Falha ao capturar screenshot.", exc_info=True)
        return None


_VALOR_RE = re.compile(r"[^\d,.-]")


def _valor_para_float(texto: str) -> Optional[float]:
    limpo = _VALOR_RE.sub("", texto or "").replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return None


async def extrair_beneficios(page: Page) -> list[dict]:
    """Expande a seção 'Recebimentos de recursos' e extrai os benefícios sociais
    (Auxílio Brasil, Auxílio Emergencial, Bolsa Família) com o detalhamento de cada um.
    """
    beneficios: list[dict] = []

    try:
        cabecalho = page.locator("button[aria-controls='accordion-recebimentos-recursos']")
        if await cabecalho.count() == 0:
            return beneficios
        await cabecalho.click()
        await page.wait_for_timeout(1000)
    except Exception:
        return beneficios

    conteudo = page.locator("#accordion-recebimentos-recursos")
    blocos = conteudo.locator(".br-table")
    total_blocos = await blocos.count()

    for i in range(total_blocos):
        bloco = blocos.nth(i)
        try:
            nome_beneficio = (await bloco.locator("strong").first.text_content() or "").strip()
        except Exception:
            continue

        links_detalhar = bloco.locator("a[href*='/beneficios/']")
        total_links = await links_detalhar.count()

        for j in range(total_links):
            href = await links_detalhar.nth(j).get_attribute("href")
            if not href:
                continue
            detalhe = await _extrair_detalhe_beneficio(page, nome_beneficio, href)
            if detalhe:
                beneficios.append(detalhe)

    return beneficios


async def _extrair_detalhe_beneficio(page: Page, nome_beneficio: str, href: str) -> Optional[dict]:
    """Abre a página de detalhamento de um benefício (parcelas) em uma aba nova
    e resume as informações relevantes.
    """
    context = page.context
    detalhe_page = await context.new_page()
    try:
        url = href if href.startswith("http") else f"{URL_PORTAL}{href}"
        await detalhe_page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await detalhe_page.wait_for_timeout(1500)
        await _aceitar_cookies(detalhe_page)

        linhas = detalhe_page.locator("table tbody tr")
        total_linhas = await linhas.count()
        if total_linhas == 0:
            return {"nome": nome_beneficio, "situacao": "Sem parcelas disponíveis"}

        valores: list[float] = []
        meses: list[str] = []
        houve_devolucao = False

        for i in range(total_linhas):
            celulas = linhas.nth(i).locator("td")
            textos = [((await celulas.nth(k).text_content()) or "").strip() for k in range(await celulas.count())]
            if len(textos) < 5:
                continue
            mes, _parcela, _uf, _municipio, *resto = textos
            valor_txt = next((t for t in resto if "R$" in t or "," in t), None)
            observacao = resto[-1] if resto else ""

            meses.append(mes)
            if valor_txt:
                valor = _valor_para_float(valor_txt)
                if valor is not None:
                    valores.append(valor)
            if "DEVOLVIDO" in observacao.upper():
                houve_devolucao = True

        return {
            "nome": nome_beneficio,
            "situacao": "Com valores devolvidos à União" if houve_devolucao else "Regular",
            "valor_ultima_parcela": valores[0] if valores else None,
            "data_ultima_parcela": meses[0] if meses else None,
            "total_recebido": round(sum(valores), 2) if valores else None,
            "periodo_inicio": meses[-1] if meses else None,
            "periodo_fim": meses[0] if meses else None,
        }
    except Exception:
        logger.warning("Falha ao extrair detalhe do benefício '%s'.", nome_beneficio, exc_info=True)
        return None
    finally:
        await detalhe_page.close()
