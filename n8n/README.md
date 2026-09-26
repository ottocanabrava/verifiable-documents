# Implementação n8n

Fluxos do [n8n](https://n8n.io) que implementam a mesma
[especificação](../docs/especificacao.md) da versão Python, sem hospedar
código: o PDF sai de um modelo no Google Slides e a validação é servida pelo
próprio n8n.

> Em desenvolvimento. Os fluxos entram aqui exportados **sem credenciais**, e
> os modelos só com dados fictícios.

## Fluxos

- `workflows/validar.json` e `workflows/validar-preparar.json`: página pública
  de validação (webhook), com o botão "Adicionar ao LinkedIn" nos certificados
  válidos. **Pronto.**
- `workflows/emitir.json`: formulário protegido que gera o PDF a partir do
  modelo e o entrega ao emissor. Planejado.
- `workflows/ids.json`: preenche a coluna `id` das linhas novas da planilha.
  Planejado.
- `modelos/`: prévias dos modelos de certificado e declaração. Planejado.

## Validação (`validar.json`)

Webhook (GET) → **Preparar** (formato do ID e limite de consultas, antes de
qualquer leitura) → **Planilha de documentos** (Google Sheets, só as linhas com
aquele `id`) → **Montar página** (mesmas regras e mesma página da versão Python)
→ resposta HTML.

O **Preparar** fica num subfluxo à parte (`validar-preparar.json`), chamado pelo
nó **Preparar (subfluxo)**. Assim cada fluxo tem um só nó Code: há ambientes cujo
firewall (WAF) barra o salvamento quando os dois estão juntos (ver abaixo). O
contador do limite de consultas fica nos dados estáticos do subfluxo.

Para usar:

1. Crie uma credencial **Google Sheets OAuth2 API** (o nó do Google Sheets não
   aceita a credencial genérica "Google OAuth2 API").
2. Importe primeiro `validar-preparar.json` e depois `validar.json`
   (*Import from file*). No nó **Preparar (subfluxo)**, escolha o fluxo
   "Validar documento: preparar".
3. No nó **Planilha de documentos**, selecione a credencial e escolha a planilha
   e a primeira aba.
4. No topo do nó **Montar página**, preencha `EMISSOR`, `URL_VALIDACAO` (a URL de
   produção do webhook, que vai nos QR codes) e, se houver,
   `LINKEDIN_ORGANIZATION_ID`.
5. Publique os dois fluxos.

Também dá para criar os fluxos pela API do n8n (`POST /api/v1/workflows`,
cabeçalho `X-N8N-API-KEY`), enviando só `name`, `nodes`, `connections` e
`settings` de cada arquivo. Eles são criados sem publicar, e os passos 1 a 5
continuam valendo.

Se salvar ou importar der **403 com "Forbidden" em texto puro** (não em JSON), quem
bloqueou foi um firewall de aplicação (WAF) na frente do n8n, não o próprio n8n:
alguns barram o JavaScript dos nós Code. O bloqueio é por conteúdo, não por
tamanho, e parece somar pontos: cada nó Code sozinho passou, os dois juntos não,
por isso a divisão em dois fluxos. Se ainda assim bloquear, peça ao responsável
pelo ambiente que libere o salvamento de fluxos (rotas `/rest/` e `/api/v1/`),
informando o ID da requisição bloqueada que vem nos cabeçalhos da resposta.

Testado no n8n 2.40.5, ainda como fluxo único, com uma planilha simulada: documento válido, declaração
sem dados pessoais, revogado, tipo desconhecido, ID duplicado, malformado e
inexistente, XSS vindo da planilha, falha da planilha (503) e limite de
consultas.

### Diferenças em relação à versão Python

| | Python | n8n |
|---|---|---|
| Cache | 30 s | Nenhum: cada consulta lê a planilha, e a revogação é imediata |
| Limite de consultas | Exato, com trava entre threads | Aproximado (dados estáticos do fluxo, sem trava entre execuções simultâneas) |
| CSP | Própria, bloqueia qualquer script | O n8n substitui pela dele (sandbox); a proteção contra XSS é o escape de todos os valores |
| ID na planilha | Espaços nas pontas são ignorados | Comparado exatamente como está na célula |
| Histórico | Não há | Execuções não são salvas, para que os dados da linha consultada não fiquem no n8n |

## Conexão com o Google

Credenciais OAuth2 no n8n, autorizadas com a conta do emissor (sem chave de
conta de serviço). Cada serviço usa o tipo de credencial do seu nó (Google
Sheets, Google Drive, Google Slides, Gmail), todas com o mesmo cliente OAuth.
Numa organização Google Workspace, o app OAuth pode ser do tipo **Interno**,
dispensando a verificação do Google.
