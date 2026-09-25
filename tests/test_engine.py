import io

import pytest
from pypdf import PdfReader

from src.engine import UnknownDocumentType, format_date_pt, parse_date, render

# Dados fictícios.
SAMPLE = {
    "id": "k7Qm2xPz9aBc",
    "tipo_documento": "certificado_curso",
    "nome": "Maria Exemplo da Silva",
    "curso": "Introdução à Análise de Dados",
    "carga_horaria": "40",
    "data_emissao": "15/03/2026",
    "status": "ativo",
}


def pdf_text(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_pdf_contem_campos_esperados():
    text = pdf_text(render(SAMPLE, issuer="Escola Exemplo"))
    for expected in (
        "CERTIFICADO DE CONCLUSÃO",
        "Maria Exemplo da Silva",
        "Introdução à Análise de Dados",
        "40 horas",
        "15 de março de 2026",
        "Escola Exemplo",
        "k7Qm2xPz9aBc",
    ):
        assert expected in text


def test_curso_longo_quebra_linha_sem_perder_texto():
    record = {**SAMPLE, "curso": "Formação Completa em Engenharia de Dados com Python, SQL e Computação em Nuvem"}
    text = " ".join(pdf_text(render(record, issuer="Escola Exemplo")).split())
    assert "Formação Completa em Engenharia de Dados com Python, SQL e Computação em Nuvem" in text


def test_tipo_desconhecido():
    with pytest.raises(UnknownDocumentType):
        render({**SAMPLE, "tipo_documento": "diploma"}, issuer="X")


def test_campo_obrigatorio_ausente():
    with pytest.raises(ValueError, match="nome"):
        render({**SAMPLE, "nome": "  "}, issuer="X")


@pytest.mark.parametrize("raw", ["2026-03-15", "15/03/2026"])
def test_parse_date_formatos(raw):
    assert format_date_pt(parse_date(raw)) == "15 de março de 2026"
