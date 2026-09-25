# Publicação no Google Cloud Run

Tudo pelo navegador, no **Cloud Shell** (o terminal do próprio console do
Google Cloud, ícone `>_` no topo). Nenhuma chave de acesso é criada: o serviço
roda com a identidade da conta de serviço, e senha/imagens ficam no Secret
Manager.

Nos comandos, troque:

- `PROJETO` pelo ID do projeto no Google Cloud;
- `CONTA` pelo e-mail da conta de serviço que lê as planilhas;
- `DOMINIO` pelo subdomínio de validação (ex.: `validar.exemplo.com.br`).

Região: `us-east1` (cota gratuita do Cloud Run e mapeamento de domínio
disponíveis).

## 0. Antes

- O projeto precisa de uma conta de faturamento vinculada (Faturamento →
  Vincular). No volume de uma escola o uso fica dentro da cota gratuita.
- Crie um **alerta de orçamento** (Faturamento → Orçamentos e alertas), por
  exemplo de R$ 5, para ser avisado de qualquer cobrança.
- As planilhas precisam estar compartilhadas com `CONTA` como Leitor.
- O domínio precisa estar verificado no Google Search Console com a mesma
  conta que vai rodar os comandos, e ter o registro DNS
  `CNAME DOMINIO -> ghs.googlehosted.com`.

## 1. Preparar o Cloud Shell

Envie para o Cloud Shell (menu `⋮` → Fazer upload): `logo.png`,
`logo_branco.png`, `assinatura.png` (cada um com menos de 64 KB) e `env.yaml`
(variáveis do emissor, modelo abaixo).

```bash
gcloud config set project PROJETO
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com sheets.googleapis.com
```

## 2. Segredos (senha e imagens)

```bash
gcloud secrets create logo --data-file=logo.png
gcloud secrets create logo-branco --data-file=logo_branco.png
gcloud secrets create assinatura --data-file=assinatura.png
read -s -p "Senha da área de emissão: " SENHA && printf '%s' "$SENHA" | \
  gcloud secrets create admin-password --data-file=- && unset SENHA

for s in logo logo-branco assinatura admin-password; do
  gcloud secrets add-iam-policy-binding $s \
    --member=serviceAccount:CONTA --role=roles/secretmanager.secretAccessor
done
```

## 3. Publicar

```bash
git clone https://github.com/ottocanabrava/verifiable-documents
cd verifiable-documents

gcloud run deploy certificados --source . --region us-east1 \
  --service-account CONTA \
  --no-invoker-iam-check \
  --max-instances 1 --memory 512Mi \
  --env-vars-file ~/env.yaml \
  --set-secrets "/imagens/logo/logo.png=logo:latest,/imagens/logo-branco/logo_branco.png=logo-branco:latest,/imagens/assinatura/assinatura.png=assinatura:latest,ADMIN_PASSWORD=admin-password:latest"
```

- `--no-invoker-iam-check` deixa a página pública sem conceder acesso a
  `allUsers` (organizações com a política de segurança padrão do Google
  bloqueiam isso).
- `--max-instances 1` mantém o rate limit em memória coerente e limita custo.
- Se perguntar para criar um repositório do Artifact Registry, responda `Y`.

Ao final aparece uma URL `https://certificados-...run.app`. Teste
`/validar` e `/emitir`.

## 4. Domínio

```bash
gcloud beta run domain-mappings create --service certificados \
  --domain DOMINIO --region us-east1
```

O certificado HTTPS do domínio leva de alguns minutos a algumas horas para
ficar pronto.

## Atualizar depois

Dentro de `verifiable-documents`: `git pull` e o mesmo `gcloud run deploy`
(os segredos e o domínio continuam). Para trocar a senha:
`printf '%s' 'NOVA' | gcloud secrets versions add admin-password --data-file=-`
e publique de novo.

## Modelo de `env.yaml`

Fica só no Cloud Shell, fora do repositório.

```yaml
SHEET_ID: "..."
CONTEUDOS_SHEET_ID: "..."
VALIDATION_BASE_URL: "https://DOMINIO/validar"
ISSUER_NOME: "..."
ISSUER_EMAIL: "..."
ISSUER_SITE: "..."
ISSUER_RAZAO_SOCIAL: "..."
ISSUER_CNPJ: "..."
ISSUER_CIDADE: "..."
ISSUER_ENDERECO: "..."
ISSUER_SIGNATARIO: "..."
ISSUER_CARGO: "..."
ISSUER_LOGO: "/imagens/logo/logo.png"
ISSUER_LOGO_BRANCO: "/imagens/logo-branco/logo_branco.png"
ISSUER_ASSINATURA: "/imagens/assinatura/assinatura.png"
```
