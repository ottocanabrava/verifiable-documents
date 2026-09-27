"""Certificado de conclusão de semestre: mesmo layout do certificado de curso.

A pedido (`semestre_conteudo` preenchido), ganha a página de conteúdo, só com
os itens daquele semestre.
"""
from .certificado_curso import PAGE_SIZE, draw_certificado, draw_conteudo  # noqa: F401

NOME = "Certificado de conclusão de semestre"
REQUIRED = ("nome", "curso", "carga_horaria")
CONTEUDO_OPCIONAL = True


def draw(c, record, issuer):
    semestre = record.get("semestre_conteudo", "")
    if semestre and not record.get("conteudo"):
        raise ValueError(f"sem conteúdo cadastrado para {record['curso']}, {semestre} (semestre_conteudo)")
    draw_certificado(c, record, issuer, "concluiu o semestre do curso de")
    if semestre:
        c.showPage()
        draw_conteudo(c, record, issuer)
