"""Servidor da página pública de validação e comandos de emissão.

    flask --app app run                    # página em /validar
    flask --app app novo-id -n 5           # IDs novos para colar na planilha
    flask --app app pdf <id>               # gera <id>.pdf a partir da planilha
"""
import os
import time

import click
from flask import Flask, render_template_string, request

from src.engine import issuer_from_env, render
from src.templates import TEMPLATES
from src.validation import clean_id, conteudo_do_curso, find, load_conteudos, load_records, new_id, public_view

app = Flask(__name__)
app.config["LOAD_RECORDS"] = load_records
app.config["LOAD_CONTEUDOS"] = load_conteudos

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
  body { margin: 0; font-family: system-ui, sans-serif; background: #f4f3f8; color: #2b2440; }
  header { background: #36296c; color: #fff; padding: 28px 16px; text-align: center; }
  header h1 { margin: 0; font-size: 1.25rem; letter-spacing: .04em; }
  header p { margin: 6px 0 0; opacity: .75; font-size: .9rem; }
  main { max-width: 520px; margin: 24px auto; padding: 0 16px; }
  form { display: flex; gap: 8px; }
  input { flex: 1; min-width: 0; padding: 10px 12px; font-size: 1rem; border: 1px solid #c9c5d6; border-radius: 8px; }
  button { padding: 10px 16px; font-size: 1rem; border: 0; border-radius: 8px; background: #ee791e; color: #fff; cursor: pointer; }
  .card { margin-top: 20px; background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .status { font-weight: 700; font-size: 1.1rem; margin: 0 0 12px; }
  .ok { color: #1d7a45; } .bad { color: #b3261e; }
  dl { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 8px 16px; }
  dt { color: #6b6780; } dd { margin: 0; font-weight: 600; }
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


def page(status, resultado=None, doc=None, doc_id=""):
    html = render_template_string(
        PAGE, resultado=resultado, doc=doc, doc_id=doc_id, emissor=os.environ.get("ISSUER_NOME", "")
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
    return page(200, "valido" if doc["valido"] else "invalido", doc, doc_id)


@app.after_request
def security_headers(response):
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
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
    template = TEMPLATES.get(str(record.get("tipo_documento", "")).strip())
    if template and "conteudo" in template.REQUIRED:
        record = {**record, "conteudo": conteudo_do_curso(app.config["LOAD_CONTEUDOS"](), record.get("curso", ""))}
    pdf = render(record, issuer_from_env(), os.environ.get("VALIDATION_BASE_URL", ""))
    path = f"{clean_id(doc_id)}.pdf"
    with open(path, "wb") as f:
        f.write(pdf)
    click.echo(path)
