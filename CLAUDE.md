# Regras do projeto

## Ponytail (https://github.com/DietrichGebert/ponytail), nível full

Antes de escrever código, pare no primeiro degrau que resolve:

1. Precisa existir? Necessidade especulativa = não fazer.
2. Já existe neste código? Reaproveite.
3. A stdlib resolve? Use.
4. Recurso nativo da plataforma resolve? Use.
5. Dependência já instalada resolve? Use. Nunca adicione uma nova pelo que poucas linhas fazem.
6. Cabe em uma linha? Uma linha.
7. Só então: o mínimo de código que funciona.

- Sem abstração não pedida. A única justificada aqui é o registro de
  templates em `src/templates/` (um módulo por `tipo_documento`).
- Sem código "pra escalar" nem scaffolding "pra depois".
- Deletar > adicionar. Menos arquivos. Menor diff, depois de entender o problema.
- Atalho consciente com teto conhecido leva comentário `# ponytail: <teto>, <quando evoluir>`.
- Nunca simplificar: validação na entrada (ex.: `id` da rota `/validar`),
  segurança (rate limit, IDs não sequenciais, nada de CPF/e-mail na
  resposta), nem o que foi pedido explicitamente.

Como usar:

- antes de abrir um PR, rodar `/ponytail-review` no diff da branch;
- numa revisão geral do projeto, rodar `/ponytail-audit`, que só gera o
  relatório e não muda nada;
- numa sessão na nuvem, o setup script precisa rodar
  `claude plugin install ponytail@ponytail`: o registro no `settings.json`
  só baixa o código, não instala o plugin.

## Estrutura

- `docs/especificacao.md` é o contrato. Regra nova entra lá primeiro e depois
  nas duas implementações: `python/` e `n8n/`.
- Testes da versão Python: `cd python && pytest`.

## Escopo da validação (0.2.0)

- Todos os tipos (certificados e declarações) têm ID, QR code e validação.
- `/validar` responde só tipo, nome, curso, carga horária e data. Nunca
  CPF, RG, endereço nem outro dado do aluno.
- PDF de declaração nunca é servido pela rota pública (contém CPF).
- Link "Adicionar ao LinkedIn" (0.3.0): só nos certificados.

## Repositório público

- Só dados fictícios. Nenhum dado real de aluno, nenhuma credencial.
- Não identificar o cliente nem expor o ambiente dele: nada de nome, domínio,
  IDs de planilhas, hospedagem contratada, custos, planos ou qual das
  implementações ele usa. A documentação fala em "ambiente" e "restrições".
- Credenciais só via variável de ambiente (ver `.env.example`).

## Versionamento

- SemVer, controle interno. Sem release formal, sem publicar em lugar nenhum.
- Sobe a versão só em marco real: 0.2.0 = validação por QR funcionando,
  0.3.0 = link do LinkedIn funcionando.
- Cada marco: uma linha no `CHANGELOG.md`, num commit com mensagem
  `Versão X.Y.Z: <resumo>`. A tag `vX.Y.Z` é criada pela Action
  "Criar tag de versão" (disparo manual), que procura essa mensagem.

## Identidade Git (obrigatória)

Antes de criar qualquer commit:

- Conferir `git config user.name` e `git config user.email`: devem ser
  `ottocanabrava` e `ottocanabrava@gmail.com`. Se estiverem diferentes,
  corrigir a configuração local do repositório antes do commit.
- Para corrigir: `git config user.name ottocanabrava` e
  `git config user.email ottocanabrava@gmail.com`.
- Nunca usar `Claude` nem `noreply@anthropic.com` como autor dos commits.
- Não adicionar a linha `Co-Authored-By` do Claude na mensagem do commit.
- Não reescrever commits antigos nem fazer push sem autorização explícita do Otto.
