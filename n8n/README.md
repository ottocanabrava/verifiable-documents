# Implementação n8n

Fluxos do [n8n](https://n8n.io) que implementam a mesma
[especificação](../docs/especificacao.md) da versão Python, sem hospedar
código: o PDF sai de um modelo no Google Slides e a validação é servida pelo
próprio n8n.

> Em desenvolvimento. Os fluxos entram aqui exportados **sem credenciais**, e
> os modelos só com dados fictícios.

## Planejado

- `workflows/validar.json`: página pública de validação (webhook), com o botão
  "Adicionar ao LinkedIn" nos certificados válidos.
- `workflows/emitir.json`: formulário protegido que gera o PDF a partir do
  modelo e o entrega ao emissor.
- `workflows/ids.json`: preenche a coluna `id` das linhas novas da planilha.
- `modelos/`: prévias dos modelos de certificado e declaração.

## Conexão com o Google

Uma credencial **Google OAuth2** no n8n, autorizada com a conta do emissor
(sem chave de conta de serviço), com os escopos de Planilhas, Drive, Slides e
envio de e-mail. Numa organização Google Workspace, o app OAuth pode ser do
tipo **Interno**, dispensando a verificação do Google.
