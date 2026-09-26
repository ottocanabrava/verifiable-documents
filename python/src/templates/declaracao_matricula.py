"""Layout da declaração de matrícula (A4 retrato).

`draw_declaracao` também serve à declaração de término de semestre, que só
muda título, abertura e situação do aluno.

Contém CPF, RG e endereço do aluno: a declaração é validável pelo ID, mas
o PDF é só para o emissor e nunca deve ser servido pela rota pública.
"""
from xml.sax.saxutils import escape

from reportlab.lib.colors import white
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

from ..qr import draw_qr
from .certificado_curso import ACCENT, DEEP, MUTED, TEXT  # também registra a Montserrat

NOME = "Declaração de matrícula"
PAGE_SIZE = A4
REQUIRED = ("nome", "curso", "cpf", "rg", "endereco")

registerFontFamily("Montserrat-Regular", normal="Montserrat-Regular", bold="Montserrat-Bold")  # <b> no Paragraph
BODY = ParagraphStyle("body", fontName="Montserrat-Regular", fontSize=10, leading=19,
                      textColor=TEXT, alignment=4)


def _b(value):
    return f"<b>{escape(value)}</b>"


def body_text(record, issuer, abertura, situacao):
    extras = []
    if record.get("dia_aula"):
        extras.append(f"com aulas semanais ({escape(record['dia_aula'])})")
    if record.get("carga_horaria"):
        extras.append(f"com carga horária de {escape(record['carga_horaria'])} horas")
    extras = (", " + " e ".join(extras)) if extras else ""

    return (
        f"{_b(issuer['razao_social'].upper())}, pessoa jurídica de direito privado, "
        f"mantenedora da {escape(issuer['nome'])}, inscrita no CNPJ sob o número "
        f"{_b(issuer['cnpj'])}, com sede na cidade de {escape(issuer['cidade'])}, "
        f"sito na {escape(issuer['endereco'])}, {abertura} "
        f"{_b(record['nome'].upper())}, inscrito(a) no CPF sob o número "
        f"{_b(record['cpf'])} e no RG {_b(record['rg'])}, residente e domiciliado(a) em "
        f"{_b(record['endereco'].upper())}, {situacao} da instituição{extras}."
    )


def draw(c, record, issuer):
    draw_declaracao(
        c, record, issuer, "DECLARAÇÃO DE MATRÍCULA",
        "declara, para os fins que sejam necessários, que",
        f"está devidamente matriculado(a) no {_b('curso de ' + record['curso'])}",
    )


def draw_declaracao(c, record, issuer, titulo, abertura, situacao):
    width, height = PAGE_SIZE
    left, right = 56, width - 56

    # Faixa superior: logo branco à esquerda, contato à direita
    band = height - 110
    c.setFillColor(DEEP)
    c.rect(0, band, width, 110, stroke=0, fill=1)
    c.setFillColor(ACCENT)
    c.rect(0, band - 4, width, 4, stroke=0, fill=1)
    if issuer.get("logo_branco"):
        c.drawImage(issuer["logo_branco"], left, band + 25, 170, 60,
                    preserveAspectRatio=True, anchor="w", mask="auto")
    else:
        c.setFillColor(white)
        c.setFont("Montserrat-Bold", 16)
        c.drawString(left, band + 48, issuer["nome"])
    c.setFillColor(white)
    c.setFont("Montserrat-Bold", 9)
    c.drawRightString(right, band + 62, issuer["nome"])
    c.setFillColor(ACCENT)
    c.setFont("Montserrat-Regular", 8.5)
    c.drawRightString(right, band + 48, issuer.get("email", ""))
    c.drawRightString(right, band + 35, issuer.get("site", ""))

    # Título à esquerda, com traço de destaque
    c.setFillColor(DEEP)
    c.setFont("Montserrat-ExtraBold", 17)
    c.drawString(left, band - 70, titulo)
    c.setFillColor(ACCENT)
    c.rect(left, band - 84, 48, 3, stroke=0, fill=1)

    p = Paragraph(body_text(record, issuer, abertura, situacao), BODY)
    _, h = p.wrap(right - left, 400)
    top = band - 120
    p.drawOn(c, left, top - h)

    # "Cidade/UF, " + data em negrito, logo abaixo do texto
    t = c.beginText(left, top - h - 45)
    t.setFillColor(TEXT)
    t.setFont("Montserrat-Regular", 10)
    t.textOut(f"{issuer['cidade']}, ")
    t.setFont("Montserrat-Bold", 10)
    t.textOut(record["data_emissao_extenso"])
    c.drawText(t)

    # Assinatura (imagem opcional, fora do repositório), à esquerda
    sig_y = top - h - 150
    if issuer.get("assinatura"):
        c.drawImage(issuer["assinatura"], left, sig_y + 4, 170, 60,
                    preserveAspectRatio=True, anchor="sw", mask="auto")
    c.setStrokeColor(DEEP)
    c.setLineWidth(1)
    c.line(left, sig_y, left + 210, sig_y)
    c.setFillColor(TEXT)
    c.setFont("Montserrat-Bold", 10)
    c.drawString(left, sig_y - 16, issuer.get("signatario", ""))
    c.setFillColor(MUTED)
    c.setFont("Montserrat-Regular", 9)
    c.drawString(left, sig_y - 30, issuer.get("cargo", ""))

    # Rodapé: ID à esquerda, QR à direita
    c.setStrokeColor(ACCENT)
    c.setLineWidth(0.8)
    c.line(left, 100, right, 100)
    c.setFillColor(MUTED)
    c.setFont("Montserrat-Regular", 8)
    c.drawString(left, 72, "Autenticidade verificável pelo QR code ou pelo ID:")
    c.setFillColor(DEEP)
    c.setFont("Montserrat-Bold", 10)
    c.drawString(left, 57, f"ID de validação: {record['id']}")

    if record.get("validacao_url"):
        draw_qr(c, record["validacao_url"], right - 64, 30, 64)
