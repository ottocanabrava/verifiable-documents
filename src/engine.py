"""Motor de geração de PDF, agnóstico de template.

Recebe um registro (uma linha da planilha, como dict), escolhe o layout
pela coluna `tipo_documento` e devolve o PDF em bytes. Nada é gravado em
disco: o PDF é sempre gerado sob demanda.
"""
import io
from datetime import date, datetime

from reportlab.pdfgen import canvas

from .templates import TEMPLATES

REQUIRED_FIELDS = ("id", "tipo_documento", "nome", "curso", "carga_horaria", "data_emissao")

MONTHS = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


class UnknownDocumentType(ValueError):
    pass


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
    missing = [f for f in REQUIRED_FIELDS if not str(record.get(f, "")).strip()]
    if missing:
        raise ValueError(f"campos obrigatórios ausentes: {', '.join(missing)}")

    tipo = str(record["tipo_documento"]).strip()
    template = TEMPLATES.get(tipo)
    if template is None:
        raise UnknownDocumentType(f"tipo_documento desconhecido: {tipo!r}")

    data = {k: str(v).strip() for k, v in record.items()}
    data["data_emissao_extenso"] = format_date_pt(parse_date(record["data_emissao"]))

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=template.PAGE_SIZE)
    c.setTitle(f"{tipo} - {data['nome']}")
    c.setAuthor(issuer)
    template.draw(c, data, issuer)
    c.showPage()
    c.save()
    return buffer.getvalue()
