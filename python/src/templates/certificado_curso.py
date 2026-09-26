"""Layout do certificado de conclusão (A4 paisagem).

`draw_certificado` também serve aos certificados de trimestre e de semestre,
que só mudam a frase antes do nome do curso. O de curso completo ganha uma
segunda página com o conteúdo do curso (`record["conteudo"]`).
"""
from xml.sax.saxutils import escape
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph

from ..qr import draw_qr

NOME = "Certificado de conclusão de curso"
PAGE_SIZE = landscape(A4)
REQUIRED = ("nome", "curso", "carga_horaria", "conteudo")

ASSETS = Path(__file__).parent / "assets"
BACKGROUND = ASSETS / "fundo_certificado.png"

for _weight in ("Regular", "Bold", "ExtraBold"):
    pdfmetrics.registerFont(TTFont(f"Montserrat-{_weight}", ASSETS / "fonts" / f"Montserrat-{_weight}.ttf"))

ACCENT = HexColor("#3DDBD9")  # turquesa: curso em destaque sobre a faixa escura
DEEP = HexColor("#0F3D3E")    # verde-petróleo da faixa
TEXT = HexColor("#1F2A2B")
MUTED = HexColor("#5F6F70")


# Fronteira entre a faixa escura e a base branca do fundo, em pt a partir da base.
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
    c.showPage()
    draw_conteudo(c, record, issuer)


def draw_certificado(c, record, issuer, conclusao):
    width, height = PAGE_SIZE
    cx = width / 2
    text_width = width - 160

    # Fundo fornecido, sem alterações.
    c.drawImage(str(BACKGROUND), 0, 0, width, height)

    # Faixa escura: cabeçalho discreto (logo + título) e o bloco nome -> curso.
    if issuer.get("logo_branco"):
        c.drawImage(issuer["logo_branco"], cx - 45, height - 72, 90, 36, preserveAspectRatio=True, mask="auto")
    _centered(c, "CERTIFICADO DE CONCLUSÃO", "Montserrat-Bold", 13, height - 102, white, tracking=3)

    _centered(c, "Certificamos que", "Montserrat-Regular", 12, 424, white, alpha=0.75)
    name_size = _centered(c, record["nome"], "Montserrat-Bold", 42, 378, white, text_width, 20)
    _centered(c, conclusao, "Montserrat-Regular", 12, 338, white, alpha=0.75)
    # O curso nunca passa de 80% do nome, para não disputar o foco com ele.
    course_size = min(34, round(name_size * 0.8))
    _centered(c, record["curso"].upper(), "Montserrat-ExtraBold", course_size, 290, ACCENT, text_width, 16, tracking=2)

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
        c.drawCentredString(width - 30 - 28, 24, "Consulte o registro")


def _conteudo_blocks(conteudo, size):
    """[(parágrafo, espaço antes, preso ao próximo)] para a lista de conteúdo."""
    heading = ParagraphStyle("h", fontName="Montserrat-Bold", fontSize=size + 1, leading=size * 1.5, textColor=DEEP)
    item = ParagraphStyle("i", fontName="Montserrat-Regular", fontSize=size, leading=size * 1.35,
                          textColor=TEXT, leftIndent=10, bulletIndent=0)
    blocks, grupo = [], None
    for semestre, texto in conteudo:
        if semestre != grupo:
            grupo = semestre
            blocks.append((Paragraph(escape(semestre), heading), size if blocks else 0, True))
        blocks.append((Paragraph(escape(texto), item, bulletText="•"), size * 0.2, False))
    return blocks


def _flow(blocks, rects, c=None):
    """Preenche as colunas de cima para baixo. Devolve False se não couber.

    Sem `c`, só mede. Um título nunca fica sozinho no fim da coluna.
    """
    col, y = 0, None
    i = 0
    while i < len(blocks):
        x, bottom, w, h = rects[col]
        y = bottom + h if y is None else y
        para, before, keep = blocks[i]
        need = para.wrap(w, h)[1] + (0 if y == bottom + h else before)
        if keep and i + 1 < len(blocks):
            need += blocks[i + 1][0].wrap(w, h)[1] + blocks[i + 1][1]
        if y - need < bottom:
            col, y = col + 1, None
            if col == len(rects):
                return False
            continue
        y -= 0 if y == bottom + h else before
        ph = para.wrap(w, h)[1]
        if c is not None:
            para.drawOn(c, x, y - ph)
        y -= ph
        i += 1
    return True


def draw_conteudo(c, record, issuer):
    width, height = PAGE_SIZE
    strip = 96

    # Cabeçalho: o topo do próprio fundo, recortado (sem elementos novos).
    c.saveState()
    path = c.beginPath()
    path.rect(0, height - strip, width, strip)
    c.clipPath(path, stroke=0, fill=0)
    c.drawImage(str(BACKGROUND), 0, 0, width, height)
    c.restoreState()
    _centered(c, "CONTEÚDO PROGRAMÁTICO", "Montserrat-Bold", 11, height - 42, white, tracking=3)
    _centered(c, record["curso"].upper(), "Montserrat-ExtraBold", 24, height - 76, ACCENT, tracking=2)

    _centered(
        c,
        f"Conteúdos abordados no curso de {record['curso']}, com carga horária total de "
        f"{record['carga_horaria']} horas.",
        "Montserrat-Regular", 10.5, height - strip - 30, TEXT, width - 120, 8,
    )

    # Duas colunas; se o conteúdo não couber, a fonte diminui até 7 pt.
    top, bottom, margin, gap = height - strip - 48, 48, 60, 36
    col_w = (width - 2 * margin - gap) / 2
    rects = [(margin + i * (col_w + gap), bottom, col_w, top - bottom) for i in (0, 1)]
    for size in (10, 9.5, 9, 8.5, 8, 7.5, 7):
        blocks = _conteudo_blocks(record["conteudo"], size)
        if _flow(blocks, rects):
            _flow(blocks, rects, c)
            break
    else:
        raise ValueError("conteúdo do curso não cabe na segunda página")

    c.setFont("Montserrat-Regular", 7.5)
    c.setFillColor(MUTED)
    c.drawString(30, 24, f"Anexo do certificado de {record['nome']} · ID de validação: {record['id']}")
