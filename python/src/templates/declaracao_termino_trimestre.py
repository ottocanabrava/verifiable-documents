"""Declaração de término de trimestre: mesmo layout da de matrícula."""
from .declaracao_matricula import PAGE_SIZE, REQUIRED, _b, draw_declaracao  # noqa: F401

NOME = "Declaração de término de trimestre"


def draw(c, record, issuer):
    draw_declaracao(
        c, record, issuer, "DECLARAÇÃO DE TÉRMINO DE TRIMESTRE",
        "declara que o trimestre de",
        f"foi concluído no {_b('CURSO DE ' + record['curso'].upper())}",
    )
