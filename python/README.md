# Implementação Python

Flask + ReportLab + gspread, em um contêiner. Segue a
[especificação](../docs/especificacao.md) do projeto: planilha, tipos de
documento, formato do ID e o que a validação pública pode mostrar.

## Estrutura

```
app.py                 /validar (público), /emitir (com senha) e comandos
src/
  engine.py            motor de geração, agnóstico de template
  validation.py        geração de ID, leitura das planilhas e visão pública
  qr.py                QR code de validação (gerador nativo do ReportLab)
  templates/           um módulo de layout por tipo de documento
    assets/            fundo do certificado e fonte Montserrat (SIL OFL)
tests/                 52 testes, incluindo o fluxo registro -> PDF -> QR -> página
Dockerfile
DEPLOY.md              publicação com Docker
.env.example           variáveis de ambiente (sem valores reais)
```

## Rodando localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Gerando um PDF de exemplo, sem planilha:

```python
from src.engine import issuer_from_env, render

record = {
    "id": "k7Qm2xPz9aBc",
    "tipo_documento": "certificado_semestre",
    "nome": "Maria Exemplo da Silva",
    "curso": "Inglês",
    "carga_horaria": "40",
    "data_emissao": "15/03/2026",
}
open("exemplo.pdf", "wb").write(render(record, issuer_from_env()))
```

## Emitindo e validando

Com o `.env` configurado (o Flask carrega o arquivo sozinho):

```bash
flask --app app novo-id -n 5    # IDs novos para a coluna `id` da planilha
flask --app app pdf <id>        # gera <id>.pdf com QR de validação
flask --app app run             # /validar (público) e /emitir (com senha)
```

- **/validar** rejeita IDs fora do formato antes de consultar a planilha,
  mostra só os campos públicos, trata como válido apenas `status = ativo` e
  limita cada IP a 10 consultas por minuto.
- **/emitir** lista os documentos com "Baixar PDF" em cada um e sugere IDs
  novos. Usa a caixa de login do navegador (senha em `ADMIN_PASSWORD`); sem
  ela configurada, a área não existe. Erros de senha contam no mesmo limite
  por IP.
- O QR code aponta para `VALIDATION_BASE_URL?id=<id>` e também é um link
  clicável no PDF.

Publicação: [`DEPLOY.md`](DEPLOY.md).

## Variáveis de ambiente

Copie `.env.example` para `.env` (já no `.gitignore`) e preencha.

| Variável | Descrição |
|---|---|
| `SHEET_ID` | Planilha de documentos (trecho entre `/d/` e `/edit` na URL) |
| `CONTEUDOS_SHEET_ID` | Planilha com o conteúdo dos cursos |
| `GOOGLE_APPLICATION_CREDENTIALS` | Opcional. Sem ela, usa a credencial padrão do Google (identidade do ambiente ou login local da CLI) |
| `VALIDATION_BASE_URL` | URL pública da página de validação (vai no QR) |
| `ISSUER_NOME`, `ISSUER_EMAIL`, `ISSUER_SITE` | Nome e contato da instituição |
| `ISSUER_RAZAO_SOCIAL`, `ISSUER_CNPJ`, `ISSUER_CIDADE`, `ISSUER_ENDERECO` | Dados da mantenedora, usados nas declarações |
| `ISSUER_SIGNATARIO`, `ISSUER_CARGO` | Quem assina |
| `ISSUER_LOGO`, `ISSUER_LOGO_BRANCO`, `ISSUER_ASSINATURA` | Caminhos das imagens, **fora** do repositório (opcionais) |
| `ADMIN_PASSWORD` | Senha da área `/emitir` |
| `TRUST_PROXY` | `1` atrás de proxy reverso, para o rate limit usar o IP real |

## Adicionando um tipo de documento

1. Crie `src/templates/<tipo>.py` com `NOME` (exibido na validação),
   `PAGE_SIZE`, `REQUIRED` (colunas obrigatórias) e `draw(c, record, issuer)`.
2. Registre o módulo em `TEMPLATES`, em `src/templates/__init__.py`.
3. Documente o tipo na [especificação](../docs/especificacao.md).
