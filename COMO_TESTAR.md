# Como testar o robô

Esse documento é um guia rápido pra você testar a API por conta própria, sem precisar mexer em código.

## 1. Ativando o ambiente e subindo a API

Abre um terminal, entra na pasta do projeto e ativa o ambiente virtual:

```bash
cd ~/desafio-full
source venv/bin/activate
uvicorn src.api.server:app --reload
```

Isso vai deixar a API rodando em `http://localhost:8000`. Deixa esse terminal aberto, rodando, enquanto você testa.

## 2. Testando pelo Swagger (o jeito mais fácil, com interface visual)

Com a API rodando, abre no navegador:

```
http://localhost:8000/docs
```

Ali aparece o endpoint `POST /consulta`. Clica em "Try it out", edita o JSON de exemplo com os dados que você quer testar, e clica em "Execute". A resposta aparece logo abaixo, já formatada.

Um exemplo de corpo pra colar:

```json
{
  "nome": "algum nome comum",
  "cpf": null,
  "filtro": null
}
```

## 3. Testando pelo terminal, se preferir

Com a API rodando, abre outro terminal (sem fechar o que está com o uvicorn) e roda:

```bash
curl -X POST http://localhost:8000/consulta \
  -H "Content-Type: application/json" \
  -d '{"nome": "algum nome"}'
```

## 4. Onde ver o resultado salvo

Toda consulta feita salva um arquivo JSON na pasta `output/`. Pra ver os mais recentes:

```bash
ls output/
cat output/<arquivo-mais-recente>.json
```

Quando a consulta dá certo, esse JSON vem com o campo `screenshot_base64` preenchido, que é a evidência da consulta em imagem. Se quiser ver essa imagem, dá pra colar esse texto em algum conversor de base64 pra imagem, ou pede pra eu gerar um comando que salva ela direto como um arquivo `.png` na sua máquina.

## Uma coisa importante antes de sair testando à vontade

Durante o reconhecimento do site, descobrimos que o Portal da Transparência tem uma proteção contra automação que não bloqueia na cara, ela degrada aos poucos. Se você mandar muitas requisições seguidas, rápido demais, o site passa a devolver respostas "de fachada" (tipo sempre "10.000 resultados", ignorando o que você buscou de verdade), sem avisar que está fazendo isso.

Por causa disso, o ideal é:

- Testar um cenário de cada vez, com uns 15 a 30 segundos de intervalo entre uma chamada e outra.
- Ficar de olho em respostas estranhas: nome vindo `null` sem motivo, benefícios vazios pra alguém que deveria ter, ou uma contagem de resultados redonda demais tipo exatamente 10.000. Se isso acontecer, é sinal de que a proteção do site ativou de novo, e o certo é esperar um tempo (de minutos a horas) antes de tentar de novo.

## Cenários que vale a pena testar

| O que testar | Exemplo de corpo da requisição |
|---|---|
| Sucesso por nome | `{"nome": "nome de alguém comum"}` |
| Sucesso por CPF | `{"cpf": "12345678900"}` (um CPF real, formatado ou não) |
| Erro, nome que não existe | `{"nome": "zzzznomeinexistentexyz999"}` |
| Erro, CPF que não existe | `{"cpf": "00000000000"}` |
| Busca com filtro | `{"nome": "sobrenome comum", "filtro": "BENEFICIÁRIO DE PROGRAMA SOCIAL"}` |
