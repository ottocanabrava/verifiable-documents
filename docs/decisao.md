# Decisão: duas implementações da mesma especificação

## Contexto

O sistema precisa rodar no ambiente de quem emite os documentos, e ambientes
diferentes impõem restrições diferentes. As que mais pesaram:

- **Hospedagem sem suporte a Python.** Planos de hospedagem compartilhada
  costumam executar só PHP/Node.js, sem acesso ao servidor.
- **Chaves de conta de serviço bloqueadas.** Organizações Google Workspace
  recentes vêm com a política de segurança padrão que proíbe criar chaves de
  conta de serviço. Desativá-la para facilitar a integração seria piorar a
  segurança do cliente; a decisão foi respeitá-la.
- **Ferramentas que a equipe já opera.** Uma plataforma de automação já em uso
  pode ser mantida pela própria equipe, sem depender de um desenvolvedor para
  cada ajuste.

## Opções

1. **Serviço Python** (`python/`): Flask + ReportLab num contêiner. Desenha o
   PDF em código, com layout adaptativo, e tem testes automatizados. Precisa de
   um ambiente que execute contêineres e, para ler as planilhas sem chave, da
   identidade do próprio ambiente.
2. **Fluxos n8n** (`n8n/`): o PDF sai de um modelo no Google Slides preenchido
   pelo fluxo, e a validação é servida pelo próprio n8n. Não exige hospedar
   código, e o acesso ao Google é feito pelo login OAuth da conta do emissor,
   sem chave.

## Decisão

Manter as duas, com uma única especificação (`especificacao.md`) como
contrato. A escolha entre elas é feita pelo ambiente: onde há como hospedar um
serviço Python, ele é a implementação de referência; onde não há, ou onde a
equipe já opera n8n, os fluxos cobrem os mesmos requisitos.

## Consequências

| | Python | n8n |
|---|---|---|
| Layout do PDF | Adaptativo (tamanho de fonte calculado para nomes longos e conteúdo extenso) | Definido no modelo; nomes muito longos dependem de uma fonte já dimensionada no modelo |
| Testes | 56 testes automatizados, incluindo fluxo completo | Validação manual dos fluxos |
| Rate limit | Por IP, em memória | Mais simples; o formato do ID é a principal proteção |
| Manutenção | Exige quem mexa em código | Ajustável pela própria equipe no editor visual |
| Integrações (e-mail, outros sistemas) | Exigiriam código novo | Nativas da plataforma |

Custo de manter as duas: toda regra nova entra primeiro na especificação e
depois nas duas implementações.
