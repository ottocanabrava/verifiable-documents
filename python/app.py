"""Servidor da página pública de validação, da emissão e comandos.

    flask --app app run                    # /validar (público) e /emitir (senha)
    flask --app app novo-id -n 5           # IDs novos para colar na planilha
    flask --app app pdf <id>               # gera <id>.pdf a partir da planilha
"""
import hmac
import io
import os
import time

import click
from flask import Flask, Response, abort, render_template_string, request, send_file
from werkzeug.middleware.proxy_fix import ProxyFix

from src.engine import issuer_from_env, render
from src.linkedin import linkedin_url
from src.templates import TEMPLATES
from src.validation import clean_id, conteudo_do_curso, find, load_conteudos, load_records, new_id, public_view

app = Flask(__name__)
app.config["LOAD_RECORDS"] = load_records
app.config["LOAD_CONTEUDOS"] = load_conteudos

# Atrás de proxy reverso (TRUST_PROXY=1), o IP real do visitante vem do
# X-Forwarded-For. Sem isso, o rate limit veria todo mundo com o IP do proxy.
# Sem proxy, o cabeçalho é ignorado (senão qualquer um poderia forjá-lo).
if os.environ.get("TRUST_PROXY") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

RATE_LIMIT = 10  # consultas por minuto, por IP
_hits = {}


def rate_limited(ip):
    # ponytail: contador em memória do processo; com vários workers/instâncias,
    # trocar por Flask-Limiter + Redis. Atrás de proxy, configurar ProxyFix.
    now = time.monotonic()
    recent = [t for t in _hits.get(ip, ()) if now - t < 60]
    limited = len(recent) >= RATE_LIMIT
    if not limited:
        recent.append(now)
    _hits[ip] = recent
    return limited


PAGE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Validação de documentos</title>
<style>
  body { margin: 0; font-family: system-ui, sans-serif; background: #f2f5f5; color: #1f2a2b; }
  header { background: #0f3d3e; color: #fff; padding: 28px 16px; text-align: center; }
  header h1 { margin: 0; font-size: 1.25rem; letter-spacing: .04em; }
  header p { margin: 6px 0 0; opacity: .75; font-size: .9rem; }
  main { max-width: 520px; margin: 24px auto; padding: 0 16px; }
  form { display: flex; gap: 8px; }
  input { flex: 1; min-width: 0; padding: 10px 12px; font-size: 1rem; border: 1px solid #c3d0d0; border-radius: 8px; }
  button { padding: 10px 16px; font-size: 1rem; border: 0; border-radius: 8px; background: #0e7c7b; color: #fff; cursor: pointer; }
  .card { margin-top: 20px; background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .status { font-weight: 700; font-size: 1.1rem; margin: 0 0 12px; }
  .ok { color: #1d7a45; } .bad { color: #b3261e; }
  dl { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 8px 16px; }
  dt { color: #5f6f70; } dd { margin: 0; font-weight: 600; }
  a.linkedin { display: block; margin-top: 16px; padding: 10px 16px; border-radius: 8px; background: #0a66c2;
               color: #fff; text-align: center; text-decoration: none; font-weight: 600; }
</style>
</head>
<body>
<header>
  <h1>VALIDAÇÃO DE DOCUMENTOS</h1>
  {% if emissor %}<p>{{ emissor }}</p>{% endif %}
</header>
<main>
  <form method="get" action="">
    <input name="id" value="{{ doc_id }}" placeholder="ID de validação" aria-label="ID de validação" maxlength="64" required>
    <button type="submit">Validar</button>
  </form>
  {% if resultado == "valido" %}
  <div class="card">
    <p class="status ok">✓ Documento válido</p>
    <dl>
      <dt>Documento</dt><dd>{{ doc.tipo }}</dd>
      <dt>Nome</dt><dd>{{ doc.nome }}</dd>
      <dt>Curso</dt><dd>{{ doc.curso }}</dd>
      {% if doc.carga_horaria %}<dt>Carga horária</dt><dd>{{ doc.carga_horaria }} horas</dd>{% endif %}
      <dt>Emissão</dt><dd>{{ doc.data_emissao }}</dd>
    </dl>
    {% if linkedin %}<a class="linkedin" href="{{ linkedin }}" target="_blank" rel="noopener noreferrer">Adicionar ao LinkedIn</a>{% endif %}
  </div>
  {% elif resultado == "invalido" %}
  <div class="card"><p class="status bad">✗ Este documento não é mais válido.</p></div>
  {% elif resultado == "nao_encontrado" %}
  <div class="card"><p class="status bad">Documento não encontrado.</p>Confira o ID e tente de novo.</div>
  {% elif resultado == "limite" %}
  <div class="card"><p class="status bad">Muitas consultas.</p>Aguarde um minuto e tente de novo.</div>
  {% endif %}
</main>
</body>
</html>"""


def page(status, resultado=None, doc=None, doc_id="", linkedin=None):
    html = render_template_string(
        PAGE, resultado=resultado, doc=doc, doc_id=doc_id, linkedin=linkedin, emissor=os.environ.get("ISSUER_NOME", "")
    )
    return html, status


@app.get("/validar")
def validar():
    raw = request.args.get("id", "")
    if not raw:
        return page(200)
    if rate_limited(request.remote_addr):
        return page(429, "limite")

    # ID malformado é rejeitado antes de qualquer consulta à planilha.
    doc_id = clean_id(raw)
    record = find(app.config["LOAD_RECORDS"](), doc_id) if doc_id else None
    if record is None:
        return page(404, "nao_encontrado", doc_id=doc_id or "")

    doc = public_view(record)
    if not doc["valido"]:
        return page(200, "invalido", doc, doc_id)

    # Só certificados válidos ganham o link do LinkedIn (declarações não).
    cert_url = f"{os.environ.get('VALIDATION_BASE_URL') or request.base_url}?id={doc_id}"
    try:
        linkedin = linkedin_url(record, cert_url, os.environ.get("ISSUER_NOME", ""),
                                os.environ.get("LINKEDIN_ORGANIZATION_ID", ""))
    except ValueError:  # data de emissão ilegível: valida, só sem o link
        linkedin = None
    return page(200, "valido", doc, doc_id, linkedin)


def pdf_for(record):
    """PDF do registro; busca o conteúdo do curso só se o tipo precisar."""
    template = TEMPLATES.get(str(record.get("tipo_documento", "")).strip())
    if template and "conteudo" in template.REQUIRED:
        record = {**record, "conteudo": conteudo_do_curso(app.config["LOAD_CONTEUDOS"](), record.get("curso", ""))}
    return render(record, issuer_from_env(), os.environ.get("VALIDATION_BASE_URL", ""))


# --- Emissão (área da escola, protegida por senha) ---

ADMIN_PAGE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Emissão de documentos</title>
<style>
  body { margin: 0; font-family: system-ui, sans-serif; background: #f2f5f5; color: #1f2a2b; }
  header { background: #0f3d3e; color: #fff; padding: 20px 16px; }
  header h1 { margin: 0; font-size: 1.1rem; letter-spacing: .04em; }
  main { max-width: 960px; margin: 20px auto; padding: 0 16px; }
  .card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); margin-bottom: 16px; }
  h2 { font-size: 1rem; margin: 0 0 8px; }
  .muted { color: #5f6f70; font-size: .9rem; }
  code { font-size: 1rem; background: #f2f5f5; padding: 2px 6px; border-radius: 4px; user-select: all; }
  .ids { display: flex; flex-wrap: wrap; gap: 8px; }
  .table { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: .9rem; }
  th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid #e1e9e9; white-space: nowrap; }
  a.btn { display: inline-block; padding: 6px 12px; border-radius: 6px; background: #0e7c7b; color: #fff; text-decoration: none; }
  .bad { color: #b3261e; }
</style>
</head>
<body>
<header><h1>EMISSÃO DE DOCUMENTOS{% if emissor %} · {{ emissor }}{% endif %}</h1></header>
<main>
  {% if erro %}<div class="card"><p class="bad"><strong>Não foi possível gerar o PDF:</strong> {{ erro }}</p>
  <p class="muted">Corrija a linha na planilha e tente de novo.</p></div>{% endif %}
  <div class="card">
    <h2>IDs novos</h2>
    <p class="muted">Para um documento novo, copie um ID para a coluna <strong>id</strong> da planilha.</p>
    <div class="ids">{% for i in novos %}<code>{{ i }}</code>{% endfor %}</div>
  </div>
  <div class="card">
    <h2>Documentos da planilha ({{ docs|length }})</h2>
    <p class="muted">Os mais recentes primeiro. Para achar um aluno, use a busca do navegador.</p>
    <div class="table"><table>
      <tr><th>Nome</th><th>Documento</th><th>Curso</th><th>Emissão</th><th>Status</th><th></th></tr>
      {% for d in docs %}
      <tr>
        <td>{{ d.nome }}</td><td>{{ d.tipo_documento }}</td><td>{{ d.curso }}</td>
        <td>{{ d.data_emissao }}</td><td>{{ d.status }}</td>
        <td>{% if d.id_ok %}<a class="btn" href="{{ url_for('emitir_pdf', doc_id=d.id) }}">Baixar PDF</a>
            {% else %}<span class="bad">ID inválido</span>{% endif %}</td>
      </tr>
      {% endfor %}
    </table></div>
  </div>
</main>
</body>
</html>"""


def require_admin():
    """Senha única da escola (ADMIN_PASSWORD), pela caixa de login do navegador."""
    expected = os.environ.get("ADMIN_PASSWORD", "")
    if not expected:
        abort(404)  # sem senha configurada, a área de emissão não existe
    auth = request.authorization
    if auth and hmac.compare_digest((auth.password or "").encode(), expected.encode()):
        return None
    if rate_limited(request.remote_addr):
        return Response("Muitas tentativas. Aguarde um minuto.", 429)
    return Response("Senha necessária.", 401, {"WWW-Authenticate": 'Basic realm="Emissao", charset="UTF-8"'})


def admin_page(records, erro=None, status=200):
    existing = {str(r.get("id", "")).strip() for r in records}
    novos = []
    while len(novos) < 5:
        i = new_id()
        if i not in existing:
            novos.append(i)
    docs = [
        {**{k: str(r.get(k, "")).strip() for k in ("id", "nome", "tipo_documento", "curso", "data_emissao", "status")},
         "id_ok": clean_id(r.get("id")) is not None}
        for r in reversed(records)
    ]
    html = render_template_string(ADMIN_PAGE, docs=docs, novos=novos, erro=erro, emissor=os.environ.get("ISSUER_NOME", ""))
    return html, status


@app.get("/emitir")
def emitir():
    denied = require_admin()
    if denied:
        return denied
    return admin_page(app.config["LOAD_RECORDS"]())


@app.get("/emitir/<doc_id>.pdf")
def emitir_pdf(doc_id):
    denied = require_admin()
    if denied:
        return denied
    records = app.config["LOAD_RECORDS"]()
    record = find(records, doc_id)
    if record is None:
        abort(404)
    try:
        pdf = pdf_for(record)
    except ValueError as e:
        return admin_page(records, erro=f"{record.get('nome', '')} ({doc_id}): {e}", status=422)
    template = TEMPLATES[str(record["tipo_documento"]).strip()]
    nome = f"{template.NOME} - {str(record.get('nome', '')).strip()}.pdf"
    return send_file(io.BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name=nome)


@app.after_request
def security_headers(response):
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.path.startswith("/emitir"):
        response.headers["Cache-Control"] = "no-store"  # dados de alunos: nada em cache
    return response


@app.cli.command("novo-id")
@click.option("-n", default=1, help="Quantos IDs gerar.")
def novo_id(n):
    """Gera IDs de validação novos para a coluna `id` da planilha."""
    for _ in range(n):
        click.echo(new_id())


@app.cli.command("pdf")
@click.argument("doc_id")
def gerar_pdf(doc_id):
    """Gera o PDF de um documento da planilha em <id>.pdf."""
    record = find(app.config["LOAD_RECORDS"](), doc_id)
    if record is None:
        raise click.ClickException("documento não encontrado")
    pdf = pdf_for(record)
    path = f"{clean_id(doc_id)}.pdf"
    with open(path, "wb") as f:
        f.write(pdf)
    click.echo(path)
