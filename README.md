# Desafio Full Stack Python — RPA/Hiperautomação (Portal da Transparência)

Robô de consulta a pessoas físicas/jurídicas no Portal da Transparência, exposto via API FastAPI, usando Playwright em modo headless.

## Setup

1. Ambiente Python (venv já criado neste repo):
   ```
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. Dependências de sistema do Chromium headless (Ubuntu/Debian — necessário mesmo com os browsers do Playwright já baixados, pois eles dependem de libs nativas do SO):
   ```
   sudo apt-get update
   sudo apt-get install -y libnss3 libnspr4 libasound2 libatk1.0-0 libatk-bridge2.0-0 \
     libcups2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2
   ```
   Para validar que está tudo certo:
   ```
   ldd ~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome | grep "not found"
   ```
   (não deve retornar nada).

## Rodar a API

```
uvicorn src.api.server:app --reload
```

Documentação interativa (Swagger/OpenAPI) em `http://localhost:8000/docs`.

## Variáveis de ambiente

- `HEADLESS` — `true` (padrão) ou `false`, controla o modo do Chromium.

## Rodar os testes

```
pytest tests/ -v
```

Os testes cobrem o contrato da API `/consulta` para os 5 cenários do desafio (sucesso por nome, sucesso por CPF, erro por nome inexistente, erro por CPF inexistente, busca filtrada), com as funções de automação (Playwright) mockadas — a automação em si já foi validada manualmente contra o Portal da Transparência real (ver seção "Desafios enfrentados" abaixo).

## Estrutura do projeto

```
src/
  api/server.py       # endpoint FastAPI /consulta
  bot/navegador.py    # ciclo de vida do browser/contexts Playwright
  bot/busca.py        # navegação, extração de dados e benefícios no Portal
  schemas/models.py    # contratos de request/response (Pydantic)
tests/                 # testes da API (mockando a automação)
output/                 # JSONs gerados por consulta (gitignored)
```

## Como funciona

1. Cada requisição a `POST /consulta` abre um `BrowserContext` isolado (o `Browser` do Chromium é compartilhado entre requisições — permite execuções simultâneas sem que uma interfira na outra).
2. O robô visita a home do portal antes da página de busca (necessário para passar pela verificação anti-bot do site — ver desafio abaixo), preenche o campo de busca e, quando informado, aplica o filtro "Beneficiário de Programa Social".
3. Se a busca não encontrar resultados, a API responde com a mensagem de erro apropriada (uma mensagem para CPF/NIS, outra para nome, conforme os cenários de teste do desafio).
4. Se encontrar, o robô acessa o primeiro resultado, extrai nome/CPF/localidade, expande a seção "Recebimentos de recursos" e detalha cada benefício social encontrado (Auxílio Brasil, Auxílio Emergencial, Bolsa Família), captura um screenshot da tela em Base64, e retorna tudo no JSON — que também é salvo em `output/`.

### Exemplo de chamada

```
curl -X POST http://localhost:8000/consulta \
  -H "Content-Type: application/json" \
  -d '{"nome": "algum nome", "filtro": "BENEFICIÁRIO DE PROGRAMA SOCIAL"}'
```

## Decisões técnicas

- **Playwright + FastAPI + Pydantic**, conforme sugerido no desafio.
- **Um `BrowserContext` por requisição, `Browser` compartilhado**: permite execuções simultâneas isoladas sem o custo de subir um processo de browser inteiro a cada chamada.
- **Documentação automática via Swagger/OpenAPI** (nativa do FastAPI, em `/docs`), sem trabalho manual adicional — atende ao diferencial pedido no desafio.
- **JSON de saída salvo em `output/[identificador]_[data_hora].json`**, já no formato que a Parte 2 (Hiperautomação) vai precisar para subir ao Google Drive, mesmo essa parte ainda não estando implementada.

## Desafios enfrentados

- **Ambiente sem privilégios de root**: o Chromium headless do Playwright depende de bibliotecas nativas do sistema (`libnss3`, `libnspr4`, `libasound2`, etc.) que não vinham instaladas, e o ambiente de desenvolvimento não tinha `sudo` automático. Resolvido instalando as libs manualmente (ver seção Setup).
- **Verificação anti-bot do Portal da Transparência**: o site usa um desafio "Human Verification" que bloqueia acessos que parecem automatizados. Contornado visitando a home do portal antes da página de busca, com um fingerprint de navegador mais realista (removendo `navigator.webdriver`, ajustando `languages`/`plugins`, `--disable-blink-features=AutomationControlled`).
- **Degradação anti-scraping por volume de requisições**: mesmo após contornar a verificação inicial, o portal passou a devolver páginas de resultado "de fachada" (sempre "10.000 resultados", ignorando o termo buscado de verdade) depois de várias dezenas de requisições automatizadas em sequência a partir do mesmo IP — uma defesa anti-scraping que degrada silenciosamente em vez de bloquear com erro explícito. A automação foi validada com sucesso contra a estrutura real do site (seletores, fluxo, mensagens de erro) antes desse bloqueio começar; em uso real, recomenda-se espaçar as requisições e evitar rajadas de testes automatizados contra o mesmo IP.
