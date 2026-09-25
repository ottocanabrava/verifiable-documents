"""Layout da declaração de matrícula (A4 retrato).

Contém CPF, RG e endereço do aluno: esse PDF é só para o emissor e nunca
deve ser servido pela rota pública de validação.
"""
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

PAGE_SIZE = A4
REQUIRED = ("nome", "curso", "cpf", "rg", "endereco")

LINK = HexColor("#3B8FD9")
GRID = HexColor("#BBBBBB")
MUTED = HexColor("#666666")

BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=17)


def _b(value):
    return f"<b>{escape(value)}</b>"


def body_text(record, issuer):
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
        f"sito na {escape(issuer['endereco'])}, declara, para os fins que sejam "
        f"necessários, que {_b(record['nome'].upper())}, inscrito(a) no CPF sob o número "
        f"{_b(record['cpf'])} e no RG {_b(record['rg'])}, residente e domiciliado(a) em "
        f"{_b(record['endereco'].upper())}, está devidamente matriculado(a) no "
        f"{_b('curso de ' + record['curso'])} da instituição{extras}."
    )


def draw(c, record, issuer):
    width, height = PAGE_SIZE
    left, right = 28, width - 28

    # Cabeçalho: logo à esquerda, contato à direita
    top, box_h, split = height - 23, 85, 238
    c.setStrokeColor(GRID)
    c.setLineWidth(0.6)
    c.rect(left - 5, top - box_h, right - left + 10, box_h)
    c.line(split, top, split, top - box_h)
    if issuer.get("logo"):
        c.drawImage(issuer["logo"], left + 5, top - box_h + 10, split - left - 20, box_h - 20,
                    preserveAspectRatio=True, mask="auto")
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(split + 7, top - 32, issuer["nome"])
    c.setFillColor(LINK)
    c.drawString(split + 7, top - 44, issuer.get("email", ""))
    c.setFillColor(black)
    c.drawString(split + 7, top - 56, issuer.get("site", ""))

    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width / 2, height - 170, "DECLARAÇÃO DE MATRÍCULA")

    p = Paragraph(body_text(record, issuer), BODY)
    _, h = p.wrap(right - left, 400)
    p.drawOn(c, left, height - 212 - h)

    # "Cidade/UF, " normal + data em negrito, alinhados à direita
    date_text = record["data_emissao_extenso"]
    c.setFont("Helvetica", 9.5)
    c.drawRightString(right - c.stringWidth(date_text, "Helvetica-Bold", 9.5), 463, f"{issuer['cidade']}, ")
    c.setFont("Helvetica-Bold", 9.5)
    c.drawRightString(right, 463, date_text)

    # Assinatura (imagem opcional, fora do repositório)
    if issuer.get("assinatura"):
        c.drawImage(issuer["assinatura"], right - 190, 372, 170, 60, preserveAspectRatio=True, mask="auto")
    c.setStrokeColor(black)
    c.line(right - 188, 367, right, 367)
    c.setFont("Helvetica", 9.5)
    c.drawRightString(right, 350, issuer.get("signatario", ""))
    c.drawRightString(right, 333, issuer.get("cargo", ""))

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    c.drawString(left, 25, f"ID de validação: {record['id']}")
