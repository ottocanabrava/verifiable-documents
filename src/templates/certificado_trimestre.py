"""Certificado de conclusão de trimestre: mesmo layout do certificado de curso."""
from .certificado_curso import PAGE_SIZE, REQUIRED, draw_certificado  # noqa: F401


def draw(c, record, issuer):
    draw_certificado(c, record, issuer, "concluiu o trimestre do curso de")
