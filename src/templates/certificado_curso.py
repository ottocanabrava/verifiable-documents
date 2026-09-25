"""Layout do certificado de conclusão de curso (A4 paisagem)."""
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit

PAGE_SIZE = landscape(A4)

ACCENT = HexColor("#1f3a5f")
TEXT = HexColor("#222222")
MUTED = HexColor("#666666")


def _fit_font_size(c, text, font, max_size, max_width, min_size=18):
    size = max_size
    while size > min_size and c.stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def draw(c, record, issuer):
    width, height = PAGE_SIZE
    cx = width / 2
    margin = 40

    # Moldura dupla
    c.setStrokeColor(ACCENT)
    c.setLineWidth(3)
    c.rect(margin, margin, width - 2 * margin, height - 2 * margin)
    c.setLineWidth(1)
    c.rect(margin + 8, margin + 8, width - 2 * (margin + 8), height - 2 * (margin + 8))

    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(cx, height - 140, "CERTIFICADO DE CONCLUSÃO")

    c.setFillColor(TEXT)
    c.setFont("Helvetica", 16)
    c.drawCentredString(cx, height - 200, "Certificamos que")

    name = record["nome"]
    text_width = width - 2 * (margin + 60)
    name_size = _fit_font_size(c, name, "Helvetica-Bold", 30, text_width)
    c.setFont("Helvetica-Bold", name_size)
    c.drawCentredString(cx, height - 245, name)

    body = (
        f"concluiu o curso {record['curso']}, "
        f"com carga horária de {record['carga_horaria']} horas."
    )
    c.setFont("Helvetica", 16)
    y = height - 290
    for line in simpleSplit(body, "Helvetica", 16, text_width):
        c.drawCentredString(cx, y, line)
        y -= 22

    c.drawCentredString(cx, 190, f"Emitido em {record['data_emissao_extenso']}.")

    # Linha de assinatura do emissor
    c.setStrokeColor(TEXT)
    c.line(cx - 130, 135, cx + 130, 135)
    c.setFont("Helvetica", 12)
    c.drawCentredString(cx, 118, issuer)

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(margin + 20, margin + 20, f"ID de validação: {record['id']}")
