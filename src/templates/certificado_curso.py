"""Layout do certificado de conclusão de curso (A4 paisagem)."""
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

PAGE_SIZE = landscape(A4)
REQUIRED = ("nome", "curso", "carga_horaria")

ASSETS = Path(__file__).parent / "assets"
BACKGROUND = ASSETS / "fundo_certificado.png"

for _weight in ("Regular", "Bold", "ExtraBold"):
    pdfmetrics.registerFont(TTFont(f"Montserrat-{_weight}", ASSETS / "fonts" / f"Montserrat-{_weight}.ttf"))

ORANGE = HexColor("#EE791E")
TEXT = HexColor("#2B2440")
MUTED = HexColor("#6B6780")


def _fit_font_size(c, text, font, max_size, max_width, min_size):
    size = max_size
    while size > min_size and c.stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def _centered(c, text, font, size, y, color, max_width=None, min_size=None):
    if max_width:
        size = _fit_font_size(c, text, font, size, max_width, min_size)
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawCentredString(PAGE_SIZE[0] / 2, y, text)


def draw(c, record, issuer):
    width, height = PAGE_SIZE
    cx = width / 2
    text_width = width - 120

    # Fundo: faixa roxa (61% superior) e base branca.
    c.drawImage(str(BACKGROUND), 0, 0, width, height)

    _centered(c, "CERTIFICADO DE CONCLUSÃO", "Montserrat-Bold", 18, height - 70, white)
    _centered(c, "Certificamos que", "Montserrat-Regular", 14, height - 120, white)
    _centered(c, record["nome"], "Montserrat-Bold", 32, height - 165, white, text_width, 16)
    _centered(c, "concluiu o curso de", "Montserrat-Regular", 14, height - 205, white)
    _centered(c, record["curso"].upper(), "Montserrat-ExtraBold", 96, height - 310, ORANGE, text_width, 28)

    _centered(
        c,
        f"Carga horária de {record['carga_horaria']} horas  ·  Emitido em {record['data_emissao_extenso']}",
        "Montserrat-Regular", 12, 190, TEXT,
    )

    # Assinatura (imagem opcional, fora do repositório) e linha do signatário
    if issuer.get("assinatura"):
        c.drawImage(issuer["assinatura"], cx - 80, 100, 160, 55, preserveAspectRatio=True, mask="auto")
    c.setStrokeColor(TEXT)
    c.line(cx - 130, 100, cx + 130, 100)
    _centered(c, issuer.get("signatario") or issuer.get("nome", ""), "Montserrat-Bold", 11, 85, TEXT)
    cargo = " · ".join(v for v in (issuer.get("cargo"), issuer.get("nome")) if v)
    _centered(c, cargo, "Montserrat-Regular", 10, 71, TEXT)

    c.setFont("Montserrat-Regular", 8)
    c.setFillColor(MUTED)
    c.drawString(30, 25, f"ID de validação: {record['id']}")
