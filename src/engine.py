"""Motor de geração de PDF, agnóstico de template.

Recebe um registro (uma linha da planilha, como dict), escolhe o layout
pela coluna `tipo_documento` e devolve o PDF em bytes. Nada é gravado em
disco: o PDF é sempre gerado sob demanda.
"""
import io
import os
from datetime import date, datetime

from reportlab.pdfgen import canvas

from .templates import TEMPLATES

MONTHS = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

# Dados do emissor, lidos de ISSUER_<CHAVE> (ver .env.example).
ISSUER_KEYS = (
    "nome", "email", "site", "razao_social", "cnpj", "cidade", "endereco",
    "signatario", "cargo", "logo", "assinatura",
)


def issuer_from_env():
    return {k: os.environ.get(f"ISSUER_{k.upper()}", "").strip() for k in ISSUER_KEYS}


def parse_date(value):
    """Aceita date, 'AAAA-MM-DD' ou 'DD/MM/AAAA' (formato comum no Sheets)."""
    if isinstance(value, date):
        return value
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"data_emissao inválida: {value!r}")


def format_date_pt(d):
    return f"{d.day} de {MONTHS[d.month - 1]} de {d.year}"


def render(record, issuer):
    data = {k: str(v).strip() for k, v in record.items() if v is not None}

    tipo = data.get("tipo_documento", "")
    template = TEMPLATES.get(tipo)
    if template is None:
        raise ValueError(f"tipo_documento desconhecido: {tipo!r}")

    missing = [f for f in ("id", "data_emissao") + template.REQUIRED if not data.get(f)]
    if missing:
        raise ValueError(f"campos obrigatórios ausentes: {', '.join(missing)}")

    data["data_emissao_extenso"] = format_date_pt(parse_date(data["data_emissao"]))

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=template.PAGE_SIZE)
    template.draw(c, data, issuer)
    c.showPage()
    c.save()
    return buffer.getvalue()
