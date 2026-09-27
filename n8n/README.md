# Implementação n8n

Fluxos do [n8n](https://n8n.io) que implementam a mesma
[especificação](../docs/especificacao.md) da versão Python, sem hospedar
código: o PDF sai de um modelo no Google Slides e a validação é servida pelo
próprio n8n.

> Validação pronta; emissão em teste. Os fluxos entram aqui
> exportados **sem credenciais**, e os modelos só com dados fictícios.

## Fluxos

- `workflows/validar.json` e `workflows/validar-preparar.json`: página pública
  de validação (webhook), com o botão "Adicionar ao LinkedIn" nos certificados
  válidos. **Pronto.**
- `workflows/emitir.json` e `workflows/emitir-autorizar.json`: área protegida
  por senha que lista os documentos da planilha e gera o PDF a partir do modelo
  no Google Slides, entregue só ao emissor. Linha sem `id` ganha um ID novo,
  gravado na planilha, na primeira emissão.

## Validação (`validar.json`)

Webhook (GET) → **Preparar** (formato do ID e limite de consultas, antes de
qualquer leitura) → **Planilha de documentos** (Google Sheets, só as linhas com
aquele `id`) → **Montar página** (mesmas regras e mesma página da versão Python)
→ resposta HTML.

O **Preparar** fica num subfluxo à parte (`validar-preparar.json`), chamado pelo
nó **Preparar (subfluxo)**. Assim cada fluxo tem um só nó Code: há ambientes cujo
firewall (WAF) barra o salvamento quando os dois estão juntos (ver abaixo). O
contador do limite de consultas fica nos dados estáticos do subfluxo.

Para usar (a planilha segue o formato da
[especificação](../docs/especificacao.md#fonte-dos-dados): uma linha por
documento, com um `id` aleatório de 12 letras ou dígitos):

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
5. Publique os dois fluxos, o subfluxo primeiro. Depois de qualquer edição,
   publique de novo: o n8n salva a edição, mas continua servindo a última
   versão publicada.

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

Testado no n8n 2.40.5, ainda como fluxo único, com uma planilha simulada:
documento válido, declaração sem dados pessoais, revogado, tipo desconhecido, ID
duplicado, malformado e inexistente, XSS vindo da planilha, falha da planilha
(503) e limite de consultas. Já em dois fluxos, testado num ambiente real com
uma linha fictícia: documento válido com o link do LinkedIn, revogado,
malformado, inexistente e limite de consultas (o contador persiste no subfluxo, e
um `X-Forwarded-For` forjado é ignorado).

### Diferenças em relação à versão Python

| | Python | n8n |
|---|---|---|
| Cache | 30 s | Nenhum: cada consulta lê a planilha, e a revogação é imediata |
| Limite de consultas | Exato, com trava entre threads | Aproximado (dados estáticos do fluxo, sem trava entre execuções simultâneas) |
| CSP | Própria, bloqueia qualquer script | O n8n substitui pela dele (sandbox); a proteção contra XSS é o escape de todos os valores |
| ID na planilha | Espaços nas pontas são ignorados | Comparado exatamente como está na célula |
| Histórico | Não há | Execuções não são salvas, para que os dados da linha consultada não fiquem no n8n |
| ID novo | Listado na emissão, colado na planilha à mão | Gerado e gravado na planilha na primeira emissão da linha |
| QR code | Desenhado no próprio serviço | Imagem de um serviço externo (`QR_API`), que vê a URL de validação, só com o ID |
| Nome longo | Fonte reduzida até caber | Tamanho fixo do modelo |

## Emissão (`emitir.json`)

Webhook (GET) → **Autorizar** (subfluxo `emitir-autorizar.json`: login com a
conta Google) → **Gerar ID** (nó Crypto, bytes aleatórios seguros) →
**Planilha de documentos** → **Preparar documento** → uma de três saídas:

- sem parâmetro: página com os documentos da planilha e um botão "Baixar PDF"
  em cada linha (`?id=` ou, para linha sem ID, `?linha=`);
- problema na linha (tipo desconhecido, campo obrigatório vazio, data
  inválida, ID duplicado): a mesma página, com o erro no topo;
- tudo certo: grava o ID novo na planilha (se for o caso), copia o modelo no
  Drive, troca os marcadores e a caixa do QR (API do Slides), exporta o PDF,
  entrega ao emissor e apaga a cópia. Se falhar depois da cópia, a cópia também
  é apagada.

Login: sem sessão, o **Autorizar** manda o navegador para o Google, com um
`state` aleatório guardado num cookie. O Google volta em `/webhook/emitir-login`;
o fluxo confere o `state`, troca o código pelo e-mail da conta (**Trocar
código** → **Conta Google**) e o subfluxo abre uma sessão de 8 horas (cookie
`HttpOnly`, `Secure`) se o e-mail estiver em `PERMITIDOS`. A lista é conferida
de novo a cada acesso: tirar um e-mail corta o acesso na hora. Sessões e
logins pendentes ficam nos dados estáticos do subfluxo.

O `certificado_curso` ainda não é emitido por aqui: falta o modelo da página do
conteúdo do curso.

Para usar, além dos passos da validação:

1. Crie dois modelos no Google Slides, um de certificado (A4 paisagem) e um de
   declaração (A4 retrato), com os marcadores abaixo escritos no texto. O QR
   entra no lugar de uma forma que contenha só `{{qr}}`.
2. Crie uma credencial **Google OAuth2 API** com o escopo
   `https://www.googleapis.com/auth/drive`, e ative as APIs do Google Drive e do
   Google Slides no projeto do cliente OAuth.
3. No mesmo cliente OAuth do Google (tipo "Aplicativo da Web"), acrescente o
   URI de redirecionamento `<n8n>/webhook/emitir-login`.
4. Importe `emitir-autorizar.json` e depois `emitir.json`. No nó **Autorizar
   (subfluxo)**, escolha "Emitir documento: autorizar"; nos dois nós de planilha,
   a credencial do Google Sheets e a planilha; nos nós de requisição (Copiar,
   Preencher, Baixar, Apagar), a credencial Google OAuth2 API.
5. No nó **Autorizar**, preencha `CLIENT_ID`, `CLIENT_SECRET`, `URL_EMISSAO` e
   `PERMITIDOS` (e-mails ou `@dominio`); sem eles, a emissão responde 404. No
   topo do **Preparar documento**, `EMISSOR`, `URL_VALIDACAO` e os IDs dos dois
   modelos.
6. Publique os dois fluxos, o subfluxo primeiro. O endereço da emissão é
   `<n8n>/webhook/emitir`.

| Marcador | Certificado | Declaração |
|---|---|---|
| `{{id}}`, `{{data}}` (por extenso) | ✓ | ✓ |
| `{{nome}}`, `{{CURSO}}` (maiúsculas), `{{carga_horaria}}`, `{{conclusao}}` ("concluiu o semestre do curso de") | ✓ | |
| `{{TITULO}}`, `{{abertura}}`, `{{NOME}}`, `{{cpf}}`, `{{rg}}`, `{{ENDERECO}}`, `{{situacao}}`, `{{curso_destaque}}`, `{{extras}}` (dia de aula e carga horária, se houver) | | ✓ |

Os textos que mudam por tipo são os mesmos da versão Python. Nas expressões,
os nós usam `$node["..."]` e não `$('...')`: o WAF citado acima também barrou o
salvamento quando `$('...')` aparecia nas expressões junto com o nó Code.

Testado num ambiente real, ainda com senha no lugar do login Google: lista de
documentos e falha no Slides (cópia apagada, erro 502 para o emissor).

## Conexão com o Google

Credenciais OAuth2 no n8n, autorizadas com a conta do emissor (sem chave de
conta de serviço): **Google Sheets OAuth2 API** nos nós de planilha e **Google
OAuth2 API** (escopo do Drive) nas chamadas ao Drive e ao Slides, as duas com o
mesmo cliente OAuth.
Numa organização Google Workspace, o app OAuth pode ser do tipo **Interno**,
dispensando a verificação do Google.
