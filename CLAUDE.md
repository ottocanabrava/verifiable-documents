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

## Repositório público

- Só dados fictícios. Nenhum dado real de aluno, nenhuma credencial.
- Credenciais só via variável de ambiente (ver `.env.example`).

## Versionamento

- SemVer, controle interno. Sem release formal, sem publicar em lugar nenhum.
- Sobe a versão só em marco real: 0.2.0 = validação por QR funcionando,
  0.3.0 = link do LinkedIn funcionando.
- Cada marco: uma linha no `CHANGELOG.md`, num commit com mensagem
  `Versão X.Y.Z: <resumo>`. A tag `vX.Y.Z` é criada pela Action
  "Criar tag de versão" (disparo manual), que procura essa mensagem.
