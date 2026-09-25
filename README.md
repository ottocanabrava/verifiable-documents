# Verifiable Documents

Gerador de documentos verificáveis (certificados de conclusão de curso,
declarações, etc.) em PDF, a partir de uma planilha do Google Sheets.

O PDF nunca é armazenado: é sempre gerado sob demanda a partir da linha
da planilha, identificada por um ID de validação não sequencial.

> Repositório de portfólio: contém apenas dados fictícios de exemplo e
> nenhuma credencial.

## Status

| Etapa | Situação |
|---|---|
| Motor de PDF + templates `certificado_curso`, `certificado_trimestre` e `certificado_semestre` | ✅ |
| Templates `declaracao_matricula` e `declaracao_termino_semestre` | ✅ |
| Leitura do Google Sheets | ✅ |
| ID de validação + QR code (todos os tipos) | ✅ |
| Rota `/validar` com rate limit | ✅ |
| Link "Adicionar ao LinkedIn" (certificados) | ⏳ |

## Estrutura

```
app.py                 página pública /validar e comandos de emissão
src/
  engine.py            motor de geração, agnóstico de template
  validation.py        geração de ID, leitura da planilha e visão pública
  qr.py                QR code de validação (gerador nativo do ReportLab)
  templates/           um módulo de layout por tipo de documento
    assets/            fundo do certificado e fonte Montserrat (SIL OFL)
tests/
CLAUDE.md              regras de desenvolvimento (Ponytail)
.env.example           variáveis de ambiente necessárias (sem valores reais)
```

## Otimização: desenvolvido com Ponytail

O desenvolvimento usa o [Ponytail](https://github.com/DietrichGebert/ponytail),
um conjunto de regras para agentes de código (Claude Code, Cursor, Copilot)
que força a solução mais simples que funciona: YAGNI, biblioteca padrão antes
de dependência nova, nenhuma abstração não pedida e o menor diff possível.
As regras aplicadas ficam em [`CLAUDE.md`](CLAUDE.md).

Na prática, neste projeto:

- **Dependências só quando a etapa precisa:** `reportlab` para o PDF,
  `gspread` para a planilha, Flask (+ `python-dotenv`, que o Flask já sabe
  usar para ler o `.env`) para a página. Nenhuma entrou antes da hora.
- **QR code sem biblioteca nova:** o ReportLab já tem gerador de QR, então o
  pacote `qrcode` previsto no plano não foi necessário.
- **Rate limit sem biblioteca nova:** um contador por IP em memória, com o
  limite documentado no código e o caminho de evolução (Flask-Limiter + Redis).
- **Uma única abstração:** o registro de templates, usado desde o primeiro
  tipo de documento. Sem classe base, fábrica ou configuração genérica.
- **Nenhum armazenamento de PDF:** o documento é gerado sob demanda, então
  não há arquivos, cache ou storage para manter.
- **Código cortado na revisão:** uma exceção customizada com um único uso
  virou `ValueError`, e os metadados de PDF que ninguém pediu foram removidos.
- **O que nunca é simplificado:** validação de entrada, rate limiting, IDs não
  sequenciais e a restrição de dados expostos na validação.

## Planilha

Uma linha por documento. O valor de `tipo_documento` escolhe o template;
colunas que um tipo não usa ficam em branco.

```
id | tipo_documento | nome | curso | carga_horaria | data_emissao | status | cpf | rg | endereco | dia_aula
```

| `tipo_documento` | Obrigatórias | Opcionais |
|---|---|---|
| `certificado_curso` | `id`, `nome`, `curso`, `carga_horaria`, `data_emissao` + conteúdo do curso na aba `Conteudos` | |
| `certificado_trimestre`, `certificado_semestre` | `id`, `nome`, `curso`, `carga_horaria`, `data_emissao` | |
| `declaracao_matricula` | `id`, `nome`, `curso`, `cpf`, `rg`, `endereco`, `data_emissao` | `dia_aula`, `carga_horaria` |
| `declaracao_termino_semestre` | mesmas da declaração de matrícula | `dia_aula`, `carga_horaria` |

`data_emissao` aceita `AAAA-MM-DD` ou `DD/MM/AAAA`.

O certificado de curso completo tem uma segunda página com o conteúdo do
curso, lido de uma planilha separada (`CONTEUDOS_SHEET_ID`), com uma linha
por item. Assim quem mantém o currículo não precisa mexer na planilha com
dados dos alunos:

```
curso | semestre | item
Inglês | 1º semestre | Apresentar-se e puxar uma conversa inicial.
Inglês | 1º semestre | Conversar sobre seus hábitos alimentares.
```

O `curso` é comparado sem diferenciar maiúsculas; os itens saem na ordem da
planilha, agrupados por `semestre`. Curso sem conteúdo cadastrado não gera
certificado de curso completo (o comando avisa). As duas planilhas são lidas
pela primeira aba, e a service account precisa ter acesso de leitura a elas
(compartilhe com o e-mail dela).

Na planilha de documentos, deixe as colunas em **Formatar > Número > Texto
simples**, para o Sheets não converter datas nem cortar zeros de CPF/RG. Se o conteúdo for longo, a fonte diminui até
caber em duas colunas.

Todos os tipos (certificados e declarações) são validáveis pelo ID. A rota
pública de validação mostra apenas tipo, nome, curso, carga horária e data,
nunca CPF, RG ou endereço. Como as declarações contêm esses dados, o PDF delas
é gerado só para o emissor e nunca é servido pela rota pública.

## Rodando localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Gerando um PDF de exemplo:

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
flask --app app novo-id -n 5    # IDs novos: cole na coluna `id` da planilha
flask --app app pdf <id>        # gera <id>.pdf com QR de validação
flask --app app run             # página pública em /validar
```

O QR code de cada documento aponta para `VALIDATION_BASE_URL?id=<id>` e também
é um link clicável no PDF. A página de validação:

- rejeita IDs fora do formato antes de consultar a planilha;
- mostra só tipo, nome, curso, carga horária e data (nunca CPF, RG ou endereço);
- trata como válido apenas o documento com `status` igual a `ativo`;
- limita cada IP a 10 consultas por minuto.

Em produção, rode atrás de um servidor WSGI (ex.: `gunicorn app:app`). O rate
limit fica na memória do processo: com vários workers, troque por
Flask-Limiter + Redis; atrás de proxy reverso, use `ProxyFix` para o IP real.

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha. O `.env` está no
`.gitignore` e nunca deve ser commitado.

| Variável | Descrição |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Caminho do JSON da service account, **fora** do repositório |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Alternativa: o conteúdo do JSON numa linha (útil em deploy) |
| `SHEET_ID` | ID da planilha de documentos (trecho entre `/d/` e `/edit` na URL) |
| `CONTEUDOS_SHEET_ID` | ID da planilha com o conteúdo dos cursos |
| `VALIDATION_BASE_URL` | URL pública da página de validação (usada no QR code) |
| `ISSUER_NOME`, `ISSUER_EMAIL`, `ISSUER_SITE` | Nome e contato da instituição (cabeçalho e assinatura) |
| `ISSUER_RAZAO_SOCIAL`, `ISSUER_CNPJ`, `ISSUER_CIDADE`, `ISSUER_ENDERECO` | Dados da mantenedora, usados no texto da declaração |
| `ISSUER_SIGNATARIO`, `ISSUER_CARGO` | Quem assina os documentos |
| `ISSUER_LOGO`, `ISSUER_LOGO_BRANCO`, `ISSUER_ASSINATURA` | Caminhos das imagens (logo colorido para a declaração, logo claro para o fundo roxo do certificado, assinatura), **fora** do repositório (opcionais) |
| `LINKEDIN_ORGANIZATION_ID` | ID da organização no LinkedIn (opcional) |

## Adicionando um novo tipo de documento

1. Crie `src/templates/<tipo>.py` com `PAGE_SIZE`, `REQUIRED` (colunas
   obrigatórias) e `draw(c, record, issuer)`.
2. Registre o módulo em `TEMPLATES`, em `src/templates/__init__.py`.
3. Use `<tipo>` na coluna `tipo_documento` da planilha.
