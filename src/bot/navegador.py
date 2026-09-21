import os
import logging
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext

from src.bot.busca import STEALTH_INIT_SCRIPT

logger = logging.getLogger(__name__)


class GerenciadorNavegador:
    """Gerencia o ciclo de vida do Playwright Browser com suporte a múltiplos contexts.

    Permite execuções simultâneas isoladas - cada consulta roda em um BrowserContext
    próprio, enquanto o browser é compartilhado.
    """

    _browser: Optional[Browser] = None
    _playwright = None

    @classmethod
    async def get_browser(cls) -> Browser:
        if cls._browser is None or not cls._browser.is_connected():
            logger.info("Inicializando Playwright browser...")
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._playwright.chromium.launch(
                headless=os.getenv("HEADLESS", "true").lower() == "true",
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            logger.info("Browser inicializado com sucesso.")
        return cls._browser

    @classmethod
    async def criar_contexto(cls) -> BrowserContext:
        browser = await cls.get_browser()
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
        await context.add_init_script(STEALTH_INIT_SCRIPT)
        return context

    @classmethod
    async def fechar(cls) -> None:
        if cls._browser and cls._browser.is_connected():
            await cls._browser.close()
            cls._browser = None
        if cls._playwright:
            await cls._playwright.stop()
            cls._playwright = None
        logger.info("Navegador encerrado.")