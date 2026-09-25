"""Declaração de término de semestre: mesmo layout da de matrícula."""
from .declaracao_matricula import PAGE_SIZE, REQUIRED, _b, draw_declaracao  # noqa: F401


def draw(c, record, issuer):
    draw_declaracao(
        c, record, issuer, "DECLARAÇÃO DE TÉRMINO DE SEMESTRE",
        "declara que o semestre de",
        f"foi concluído no {_b('CURSO DE ' + record['curso'].upper())}",
    )
