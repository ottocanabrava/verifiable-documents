"""Certificado de conclusão de semestre: mesmo layout do certificado de curso."""
from .certificado_curso import PAGE_SIZE, draw_certificado  # noqa: F401

NOME = "Certificado de conclusão de semestre"
REQUIRED = ("nome", "curso", "carga_horaria")


def draw(c, record, issuer):
    draw_certificado(c, record, issuer, "concluiu o semestre do curso de")
