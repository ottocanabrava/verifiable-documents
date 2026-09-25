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
| Motor de PDF + template `certificado_curso` | ✅ |
| Templates `declaracao_matricula` e `declaracao_termino_semestre` | ✅ |
| Leitura do Google Sheets | ⏳ |
| ID de validação + QR code | ⏳ |
| Link "Adicionar ao LinkedIn" | ⏳ |
| Rota `/validar` | ⏳ |

## Estrutura

```
src/
  engine.py            motor de geração, agnóstico de template
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

- **Uma dependência de execução** (`reportlab`) nesta etapa. `gspread`,
  `qrcode` e Flask só entram quando a etapa que usa cada um for construída.
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
| `certificado_curso` | `id`, `nome`, `curso`, `carga_horaria`, `data_emissao` | |
| `declaracao_matricula` | `id`, `nome`, `curso`, `cpf`, `rg`, `endereco`, `data_emissao` | `dia_aula`, `carga_horaria` |
| `declaracao_termino_semestre` | mesmas da declaração de matrícula | `dia_aula`, `carga_horaria` |

`data_emissao` aceita `AAAA-MM-DD` ou `DD/MM/AAAA`.

As declarações contêm CPF, RG e endereço: elas são geradas só para
o emissor e nunca é servida pela rota pública de validação, que mostra apenas
nome, curso, carga horária e data.

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
    "tipo_documento": "certificado_curso",
    "nome": "Maria Exemplo da Silva",
    "curso": "Inglês",
    "carga_horaria": "40",
    "data_emissao": "15/03/2026",
}
open("exemplo.pdf", "wb").write(render(record, issuer_from_env()))
```

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha. O `.env` está no
`.gitignore` e nunca deve ser commitado.

| Variável | Descrição |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Caminho do JSON da service account, **fora** do repositório |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Alternativa: o conteúdo do JSON numa linha (útil em deploy) |
| `SHEET_ID` | ID da planilha (trecho entre `/d/` e `/edit` na URL) |
| `SHEET_TAB` | Nome da aba com os dados |
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
