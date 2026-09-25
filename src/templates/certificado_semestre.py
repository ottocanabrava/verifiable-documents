"""Certificado de conclusão de semestre: mesmo layout do certificado de curso."""
from .certificado_curso import PAGE_SIZE, REQUIRED, draw_certificado  # noqa: F401

NOME = "Certificado de conclusão de semestre"


def draw(c, record, issuer):
    draw_certificado(c, record, issuer, "concluiu o semestre do curso de")
