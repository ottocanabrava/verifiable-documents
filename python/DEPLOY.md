# Publicação (Docker)

A implementação Python roda em qualquer lugar que execute um contêiner:
um servidor com Docker ou uma plataforma de contêineres. O que muda de um
ambiente para outro é só onde ficam as variáveis e os arquivos secretos.

## 1. Imagem

```bash
docker build -t verifiable-documents .
```

A imagem roda o `gunicorn` com **um processo** (o rate limit fica em memória):
rode **uma única instância** do contêiner.

## 2. Configuração

- Variáveis: as do `.env.example` (IDs das planilhas, dados do emissor,
  `VALIDATION_BASE_URL`, `ADMIN_PASSWORD`), num arquivo de ambiente **fora do
  repositório** ou no cofre de segredos da plataforma.
- O contêiner roda com um usuário sem privilégios: os arquivos montados
  (imagens e, se houver, a credencial) precisam ter permissão de leitura para
  ele (por exemplo, `chmod 644`).
- Imagens do emissor (logo, logo claro, assinatura): montadas como arquivos
  somente leitura, com os caminhos em `ISSUER_LOGO`, `ISSUER_LOGO_BRANCO` e
  `ISSUER_ASSINATURA`.
- Acesso às planilhas: de preferência pela identidade do próprio ambiente
  (sem chave). Se for preciso um arquivo de credencial, monte-o como segredo
  e aponte `GOOGLE_APPLICATION_CREDENTIALS` para ele.

```bash
docker run -d --name verifiable-documents --restart unless-stopped \
  -p 127.0.0.1:8080:8080 -e PORT=8080 -e TRUST_PROXY=1 \
  --env-file /caminho/seguro/producao.env \
  -v /caminho/seguro/imagens:/imagens:ro \
  verifiable-documents
```

## 3. HTTPS

Coloque um proxy reverso com HTTPS na frente (Caddy, Nginx, Traefik ou o da
plataforma) apontando para a porta do contêiner, e mantenha `TRUST_PROXY=1`
para o rate limit enxergar o IP real de cada visitante. Sem proxy na frente,
use `TRUST_PROXY=0`.

## 4. Conferir

- `https://SEU_DOMINIO/validar` abre a página de validação.
- `https://SEU_DOMINIO/emitir` pede a senha de `ADMIN_PASSWORD`.
- O QR dos PDFs aponta para `VALIDATION_BASE_URL?id=<id>`.

## Atualizar

`git pull`, `docker build` de novo e recrie o contêiner com o mesmo
`docker run`.
