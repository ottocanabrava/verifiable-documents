# Implementação n8n

Fluxos do [n8n](https://n8n.io) que implementam a mesma
[especificação](../docs/especificacao.md) da versão Python, sem hospedar
código: o PDF sai de um modelo no Google Slides e a validação é servida pelo
próprio n8n.

> Validação pronta; emissão publicada e testada até a geração do PDF, que
> ainda depende da configuração do Google no ambiente. Os fluxos entram aqui
> exportados **sem credenciais** nem dados da escola: os valores de
> configuração ficam só no n8n.

## Fluxos

- `workflows/validar.json` e `workflows/validar-preparar.json`: página pública
  de validação (webhook), com o botão "Adicionar ao LinkedIn" nos certificados
  válidos. **Pronto.**
- `workflows/qr.json`: QR code de validação desenhado no próprio n8n (PNG, sem
  biblioteca nem serviço externo), que o Slides busca por
  `<n8n>/webhook/qr?id=<id>`. Só aceita IDs no formato e só codifica o endereço
  de validação configurado. Cor e logo no centro são opcionais (`COR` e `LOGO`); com
  logo, usa a correção de erros mais alta (H) e a margem branca da norma.
- `workflows/emitir*.json`: área com login pela conta Google onde a equipe
  cadastra documentos (formulário) e baixa o PDF gerado a partir do modelo no
  Google Slides, entregue só a ela, um por vez ou vários num ZIP. Também
  importa um CSV com vários documentos. Um fluxo principal e sete subfluxos
  (autorizar, identidade visual, pacote ZIP e uma tela cada: login, lista,
  formulário, importar CSV).

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
   `LINKEDIN_ORGANIZATION_ID`. A identidade visual é opcional: `LOGO_URL`, `COR`
   (cabeçalho e botão) e `COR_DESTAQUE` (faixa sob o cabeçalho). Em branco, a
   página fica como no exemplo do README principal.
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
| Acesso à emissão | Senha, com limite de tentativas | Login com a conta Google (e-mails ou domínio autorizados) |
| Cadastro | Direto na planilha | Formulário, CSV com vários documentos ou direto na planilha |
| ID novo | Listado na emissão, colado na planilha à mão | Gerado no cadastro, ou na primeira emissão de uma linha sem ID |
| Vários PDFs | Um por vez | Vários num ZIP (até 15 por vez) |
| Nome do PDF | "Tipo - Nome completo.pdf" | "Nome Último-sobrenome - Tipo.pdf" |
| QR code | Desenhado no próprio serviço | Desenhado no fluxo `qr.json` (cor opcional), buscado pelo Slides |
| Nome longo | Fonte reduzida até caber | Tamanho fixo do modelo |

## Emissão (`emitir.json`)

Webhook (GET e POST) → **Autorizar** (subfluxo `emitir-autorizar.json`: login
com a conta Google) → **Gerar ID** (nó Crypto, bytes aleatórios seguros) →
(se veio um CSV, **Ler CSV** antes) → **Planilha de documentos** → **Preparar
documento** → uma destas saídas:

- sem parâmetro: lista dos documentos da planilha, com o nome legível do tipo,
  a situação e um botão "Baixar PDF" em cada um (`?id=` ou, para linha sem ID,
  `?linha=`), em cartões que cabem no celular;
- `?novo`: formulário de cadastro. CPF, RG, endereço e dia de aula só aparecem
  quando o tipo é declaração (CSS, sem script). O envio (POST no mesmo
  endereço) passa pelas mesmas conferências da emissão, ganha um ID novo, é
  gravado na planilha como texto puro (**Anotar na planilha**) e volta para a
  lista com o botão de baixar o PDF do documento novo. Com erro, o formulário
  volta preenchido e com o aviso;
- `?importar`: envio de um CSV (separado por `;`, `,` ou tabulação; colunas como
  na planilha, com sinônimos como "tipo" e "data"; o tipo pode vir pelo nome,
  como "Declaração de matrícula"), até 100 documentos. Tudo ou nada: com erro em
  alguma linha, nada é gravado e a tela lista as linhas a corrigir. Com tudo
  certo, grava todos e volta para a lista com "Baixar todos (ZIP)", em partes de
  até 15;
- `?zip=<id>,<id>…` (ou os marcados na lista): gera os PDFs, dá a cada um o
  nome do arquivo (numerando nomes repetidos), compacta no subfluxo **pacote
  ZIP** e entrega "Documentos DD-MM-AAAA.zip". Até 15 por vez, porque o ZIP é
  montado dentro da requisição e uma conexão longa cai por tempo;
- problema na linha (tipo desconhecido, campo obrigatório vazio, data
  inválida, ID duplicado): a lista, com o erro no topo;
- tudo certo: grava o ID novo na planilha (se for o caso), copia o modelo no
  Drive, troca os marcadores e a caixa do QR (API do Slides), exporta o PDF,
  entrega ao emissor (arquivo "Nome Último-sobrenome - Tipo do documento.pdf")
  e apaga a cópia (em paralelo à entrega; no ZIP, todas as cópias). Se falhar depois da cópia, a cópia também
  é apagada.

Login: sem sessão, o **Autorizar** mostra a tela de login, no leiaute do login
do Google, com o logo da escola e o botão "Fazer login com o Google" (padrão
visual do Google, sem script: é um link), com um `state`
aleatório guardado num cookie. O Google volta em `/webhook/emitir-login`; o
fluxo confere o `state`, troca o código pelo e-mail da conta (**Trocar
código** → **Conta Google**) e o subfluxo abre uma sessão de 8 horas (cookie
`HttpOnly`, `Secure`, `SameSite=Lax`, que também barra o envio do formulário a
partir de outro site) se o e-mail estiver em `PERMITIDOS`. A lista é conferida
de novo a cada acesso: tirar um e-mail corta o acesso na hora. Sessões e
logins pendentes ficam nos dados estáticos do subfluxo.

O **Preparar documento** só devolve dados, com os textos já escapados; o HTML
fica nos subfluxos de tela, em expressões do nó Set, e a cor, o logo e o nome
da escola no subfluxo de identidade visual.

O `certificado_curso` usa um modelo de duas páginas: a primeira igual à dos
outros certificados e a segunda com o conteúdo programático, lido da aba de
conteúdos (`curso | semestre | item`, como na
[especificação](../docs/especificacao.md#fonte-dos-dados); pode ser uma aba da
mesma planilha, escolhida no nó **Conteúdo dos cursos**). Os itens do curso
(sem diferenciar maiúsculas) saem na ordem da aba, com o semestre em
maiúsculas como título, enchendo a primeira coluna e seguindo na segunda.

O `certificado_semestre` usa o mesmo modelo de duas páginas quando
`semestre_conteudo` está preenchida (no formulário, o campo "Página de
conteúdo", que só aparece nesse tipo e lista os semestres da aba; no CSV, a
coluna de mesmo nome). A segunda página traz só os itens daquele semestre, e a
frase de abertura diz "no 1º semestre do curso de…". O cadastro já confere se
há conteúdo para o curso e o semestre escolhidos. Sem conteúdo cadastrado, ou com
conteúdo que não cabe na página (cerca de 26 linhas por coluna), o PDF não é
gerado e a tela diz o porquê. Os títulos de semestre saem em maiúsculas; com os
IDs das duas caixas de conteúdo do modelo em `CAIXAS_CONTEUDO` (lidos uma vez
pela API do Slides), saem como escritos na aba, em negrito e na `COR_TITULOS`.

Para usar, além dos passos da validação:

1. Crie três modelos no Google Slides: certificado (A4 paisagem), certificado de
   curso (o mesmo, com uma segunda página de conteúdo) e declaração (A4
   retrato), com os marcadores abaixo escritos no texto. O QR
   entra no lugar de uma forma que contenha só `{{qr}}`.
2. Crie uma credencial **Google OAuth2 API** com o escopo
   `https://www.googleapis.com/auth/drive`, e ative as APIs do Google Drive e do
   Google Slides no projeto do cliente OAuth.
3. No mesmo cliente OAuth do Google (tipo "Aplicativo da Web"), acrescente o
   URI de redirecionamento `<n8n>/webhook/emitir-login`.
4. Importe os sete subfluxos (`emitir-autorizar.json`, `emitir-identidade.json`,
   `emitir-zip.json` e os quatro `emitir-tela-*.json`) e depois `emitir.json`. Nos nós
   **Autorizar (subfluxo)** e **Criar sessão (subfluxo)**, escolha "Emitir
   documento: autorizar"; nos nós **Identidade**, **Tela de login**, **Lista**,
   **Formulário**, **Importar CSV** e **Pacote ZIP (subfluxo)**, o subfluxo
   correspondente; nos quatro nós de
   planilha, a credencial do Google Sheets e a planilha (no **Conteúdo dos
   cursos**, a aba de conteúdos); nos nós de requisição
   (Copiar, Preencher, Baixar, Apagar), a credencial Google OAuth2 API.
5. No nó **Autorizar**, preencha `CLIENT_ID`, `CLIENT_SECRET`, `URL_EMISSAO` e
   `PERMITIDOS` (e-mails ou `@dominio`); sem eles, a emissão responde 404. No
   subfluxo de identidade visual, `emissor`, `logo_url` (opcional) e `cor`. No
   topo do **Preparar documento**, `URL_VALIDACAO`, `URL_QR` (o endereço de
   produção do fluxo `qr.json`, publicado antes) e os IDs dos três modelos. No
   `qr.json`, `URL_VALIDACAO` e, se quiser, a `COR` dos módulos (escura).
6. Publique todos os fluxos, os subfluxos primeiro. O endereço da emissão é
   `<n8n>/webhook/emitir`.

| Marcador | Certificado | Declaração |
|---|---|---|
| `{{id}}`, `{{data}}` (por extenso) | ✓ | ✓ |
| `{{nome}}`, `{{CURSO}}` (maiúsculas), `{{carga_horaria}}`, `{{conclusao}}` ("concluiu o semestre do curso de") | ✓ | |
| 2ª página (conteúdo): `{{CURSO}}`, `{{introducao}}` (frase de abertura), `{{conteudo_1}}` e `{{conteudo_2}}` (uma caixa por coluna), `{{nome}}`, `{{id}}` | ✓ | |
| `{{TITULO}}`, `{{abertura}}`, `{{NOME}}`, `{{cpf}}`, `{{rg}}`, `{{ENDERECO}}`, `{{situacao}}`, `{{curso_destaque}}`, `{{extras}}` (dia de aula e carga horária, se houver) | | ✓ |

Os textos que mudam por tipo são os mesmos da versão Python.

Por que tantos subfluxos: o WAF citado acima soma pontos pelo conteúdo do fluxo
salvo. Barrou o nó Code junto com uma página HTML, duas telas HTML no mesmo
fluxo e `$('...')` nas expressões junto com o nó Code (daí `$node["..."]`).
Cada tela sozinha passa.

Testado num ambiente real: importação de CSV (com erros: nada gravado e linhas
apontadas; válido, com `;`, BOM, aspas e tipo pelo nome: gravado e volta para a
lista com o ZIP), pedido de ZIP até o Slides (cópias apagadas na falha), lista,
formulário (campo faltando, HTML no nome
escapado, cadastro gravado na planilha, sem CPF por ser certificado, e volta
para a lista com o documento novo), tela de login (cookie do `state` passando
pelo proxy) e volta do Google com `state` errado (tela de novo, com aviso) ou
código falso (erro 502). Antes, ainda com senha no lugar do login: falha no
Slides (cópia apagada, erro 502 para o emissor). Falta o login de ponta a ponta
e a geração do PDF, que dependem da configuração do Google.

## Conexão com o Google

Credenciais OAuth2 no n8n, autorizadas com a conta do emissor (sem chave de
conta de serviço): **Google Sheets OAuth2 API** nos nós de planilha e **Google
OAuth2 API** (escopo do Drive) nas chamadas ao Drive e ao Slides, as duas com o
mesmo cliente OAuth. No projeto desse cliente, ative as APIs do Google Sheets,
do Google Drive e do Google Slides.

O login da emissão usa o mesmo cliente OAuth (tipo "Aplicativo da Web"), com o
ID e a chave secreta no nó **Autorizar** e `<n8n>/webhook/emitir-login` entre
os URIs de redirecionamento autorizados. Ele só pede `openid email`: o fluxo
recebe o e-mail de quem entrou, e nada mais da conta.
Numa organização Google Workspace, o app OAuth pode ser do tipo **Interno**,
dispensando a verificação do Google.
