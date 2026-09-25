"""Layout do certificado de conclusão (A4 paisagem).

`draw_certificado` também serve aos certificados de trimestre e de semestre,
que só mudam a frase antes do nome do curso.
"""
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ..qr import draw_qr

NOME = "Certificado de conclusão de curso"
PAGE_SIZE = landscape(A4)
REQUIRED = ("nome", "curso", "carga_horaria")

ASSETS = Path(__file__).parent / "assets"
BACKGROUND = ASSETS / "fundo_certificado.png"

for _weight in ("Regular", "Bold", "ExtraBold"):
    pdfmetrics.registerFont(TTFont(f"Montserrat-{_weight}", ASSETS / "fonts" / f"Montserrat-{_weight}.ttf"))

ORANGE = HexColor("#EE791E")
TEXT = HexColor("#2B2440")
MUTED = HexColor("#6B6780")


# Fronteira entre a faixa roxa e a base branca do fundo, em pt a partir da base.
BAND_EDGE = 231


def _fit_font_size(c, text, font, max_size, max_width, min_size):
    size = max_size
    while size > min_size and c.stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def _centered(c, text, font, size, y, color, max_width=None, min_size=None, tracking=0, alpha=1):
    """Texto centralizado; `tracking` = espaço extra entre letras, em pt."""
    if max_width:
        size = _fit_font_size(c, text, font, size, max_width - tracking * len(text), min_size)
    w = c.stringWidth(text, font, size) + tracking * (len(text) - 1)
    t = c.beginText(PAGE_SIZE[0] / 2 - w / 2, y)
    t.setFont(font, size)
    t.setCharSpace(tracking)
    t.textOut(text)
    c.setFillColor(color)
    c.setFillAlpha(alpha)
    c.drawText(t)
    c.setFillAlpha(1)
    return size


def draw(c, record, issuer):
    draw_certificado(c, record, issuer, "concluiu o curso de")


def draw_certificado(c, record, issuer, conclusao):
    width, height = PAGE_SIZE
    cx = width / 2
    text_width = width - 160

    # Fundo fornecido, sem alterações.
    c.drawImage(str(BACKGROUND), 0, 0, width, height)

    # Faixa roxa: cabeçalho discreto (logo + título) e o bloco nome -> curso.
    if issuer.get("logo_branco"):
        c.drawImage(issuer["logo_branco"], cx - 45, height - 72, 90, 36, preserveAspectRatio=True, mask="auto")
    _centered(c, "CERTIFICADO DE CONCLUSÃO", "Montserrat-Bold", 13, height - 102, white, tracking=3)

    _centered(c, "Certificamos que", "Montserrat-Regular", 12, 424, white, alpha=0.75)
    name_size = _centered(c, record["nome"], "Montserrat-Bold", 42, 378, white, text_width, 20)
    _centered(c, conclusao, "Montserrat-Regular", 12, 338, white, alpha=0.75)
    # O curso nunca passa de 80% do nome, para não disputar o foco com ele.
    course_size = min(34, round(name_size * 0.8))
    _centered(c, record["curso"].upper(), "Montserrat-ExtraBold", course_size, 290, ORANGE, text_width, 16, tracking=2)

    # Base branca: complementares, data/local e assinatura.
    _centered(c, f"Carga horária: {record['carga_horaria']} horas", "Montserrat-Regular", 11, 192, TEXT)
    local = f"{issuer['cidade']}, " if issuer.get("cidade") else ""
    _centered(c, local + record["data_emissao_extenso"], "Montserrat-Regular", 11, 175, MUTED)

    if issuer.get("assinatura"):
        c.drawImage(issuer["assinatura"], cx - 75, 94, 150, 48, preserveAspectRatio=True, mask="auto")
    c.setStrokeColor(MUTED)
    c.setLineWidth(0.6)
    c.line(cx - 110, 92, cx + 110, 92)
    _centered(c, issuer.get("signatario") or issuer.get("nome", ""), "Montserrat-Bold", 10.5, 77, TEXT)
    _centered(c, issuer.get("cargo", ""), "Montserrat-Regular", 9, 64, MUTED)

    # Rodapé institucional, no menor peso da página.
    c.setFont("Montserrat-Regular", 7.5)
    c.setFillColor(MUTED)
    rodape = " · ".join(v for v in (issuer.get("nome"), f"ID de validação: {record['id']}") if v)
    c.drawString(30, 24, rodape)

    # QR de validação no canto inferior direito, fora do eixo central.
    if record.get("validacao_url"):
        draw_qr(c, record["validacao_url"], width - 30 - 56, 34, 56)
        c.setFont("Montserrat-Regular", 6.5)
        c.drawCentredString(width - 30 - 28, 24, "Verifique a autenticidade")
