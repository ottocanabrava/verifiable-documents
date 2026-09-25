import io

import pytest
from pypdf import PdfReader

from src.engine import format_date_pt, parse_date, render

# Dados fictícios.
ISSUER = {
    "nome": "Escola Exemplo de Idiomas",
    "email": "contato@exemplo.com.br",
    "site": "www.exemplo.com.br",
    "razao_social": "Escola Exemplo Ltda",
    "cnpj": "00.000.000/0001-00",
    "cidade": "Cidade Exemplo/UF",
    "endereco": "Rua das Flores, 100, Bairro: Centro, CEP 00.000-000",
    "signatario": "Ana Exemplo",
    "cargo": "Diretora Pedagógica",
}

# Conteúdo fictício com o volume de um curso real: 4 semestres x 12 itens.
CONTEUDO = [
    (f"{s}º semestre", f"Tópico fictício {i} do {s}º semestre: conversar sobre um tema do cotidiano.")
    for s in range(1, 5)
    for i in range(1, 13)
]

CERTIFICADO = {
    "id": "k7Qm2xPz9aBc",
    "tipo_documento": "certificado_curso",
    "nome": "Maria Exemplo da Silva",
    "curso": "Inglês",
    "carga_horaria": "40",
    "data_emissao": "15/03/2026",
    "status": "ativo",
    "conteudo": CONTEUDO,
}

DECLARACAO = {
    "id": "Zr4tW8nLq2Ys",
    "tipo_documento": "declaracao_matricula",
    "nome": "João Exemplo Souza",
    "curso": "espanhol",
    "cpf": "000.000.000-00",
    "rg": "00000000",
    "endereco": "Rua Fictícia, Nº 1, Bairro: Jardim, Município: Cidade/UF",
    "data_emissao": "2026-09-14",
    "status": "ativo",
}


def pdf_text(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return " ".join(" ".join(page.extract_text() for page in reader.pages).split())


def test_certificado_contem_campos_esperados():
    text = pdf_text(render(CERTIFICADO, ISSUER))
    for expected in (
        "CERTIFICADO DE CONCLUSÃO",
        "Maria Exemplo da Silva",
        "INGLÊS",
        "40 horas",
        "15 de março de 2026",
        "Ana Exemplo",
        "Escola Exemplo de Idiomas",
        "k7Qm2xPz9aBc",
    ):
        assert expected in text


@pytest.mark.parametrize("periodo", ["trimestre", "semestre"])
def test_certificado_por_periodo(periodo):
    text = pdf_text(render({**CERTIFICADO, "tipo_documento": f"certificado_{periodo}"}, ISSUER))
    assert f"concluiu o {periodo} do curso de INGLÊS" in text


def test_certificado_curso_tem_pagina_de_conteudo():
    reader = PdfReader(io.BytesIO(render(CERTIFICADO, ISSUER)))
    assert len(reader.pages) == 2
    page2 = " ".join(reader.pages[1].extract_text().split())
    assert "CONTEÚDO PROGRAMÁTICO" in page2 and "carga horária total de 40 horas" in page2
    for s in range(1, 5):
        assert f"{s}º semestre" in page2
        assert f"Tópico fictício 12 do {s}º semestre" in page2
    assert "Anexo do certificado de Maria Exemplo da Silva" in page2


def test_certificado_de_periodo_tem_uma_pagina():
    pdf = render({**CERTIFICADO, "tipo_documento": "certificado_semestre", "conteudo": []}, ISSUER)
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 1


def test_certificado_curso_sem_conteudo():
    with pytest.raises(ValueError, match="conteudo"):
        render({**CERTIFICADO, "conteudo": []}, ISSUER)


def test_conteudo_que_nao_cabe():
    enorme = [("1º semestre", "Item muito longo " * 20)] * 60
    with pytest.raises(ValueError, match="não cabe"):
        render({**CERTIFICADO, "conteudo": enorme}, ISSUER)


def test_certificado_curso_longo_nao_perde_texto():
    record = {**CERTIFICADO, "curso": "Inglês para Negócios Avançado"}
    assert "INGLÊS PARA NEGÓCIOS AVANÇADO" in pdf_text(render(record, ISSUER))


def test_declaracao_contem_campos_esperados():
    text = pdf_text(render(DECLARACAO, ISSUER))
    for expected in (
        "DECLARAÇÃO DE MATRÍCULA",
        "ESCOLA EXEMPLO LTDA",
        "00.000.000/0001-00",
        "JOÃO EXEMPLO SOUZA",
        "000.000.000-00",
        "RUA FICTÍCIA, Nº 1",
        "matriculado(a) no curso de espanhol da instituição.",
        "Cidade Exemplo/UF, 14 de setembro de 2026",
        "Zr4tW8nLq2Ys",
    ):
        assert expected in text


def test_declaracao_termino_semestre():
    record = {**DECLARACAO, "tipo_documento": "declaracao_termino_semestre", "curso": "Inglês"}
    text = pdf_text(render(record, ISSUER))
    assert "DECLARAÇÃO DE TÉRMINO DE SEMESTRE" in text
    assert "declara que o semestre de JOÃO EXEMPLO SOUZA, inscrito(a) no CPF" in text
    assert "foi concluído no CURSO DE INGLÊS da instituição." in text


def test_declaracao_dia_aula_e_carga_horaria_opcionais():
    record = {**DECLARACAO, "dia_aula": "terça-feira, das 19h às 20h30", "carga_horaria": "60"}
    text = pdf_text(render(record, ISSUER))
    assert (
        "da instituição, com aulas semanais (terça-feira, das 19h às 20h30) "
        "e com carga horária de 60 horas." in text
    )


def test_declaracao_escapa_caracteres_especiais():
    record = {**DECLARACAO, "nome": "Ana <b>& Cia"}
    assert "ANA <B>& CIA" in pdf_text(render(record, ISSUER))


def test_tipo_desconhecido():
    with pytest.raises(ValueError, match="tipo_documento"):
        render({**CERTIFICADO, "tipo_documento": "diploma"}, ISSUER)


@pytest.mark.parametrize("record, campo", [(CERTIFICADO, "carga_horaria"), (DECLARACAO, "cpf")])
def test_campo_obrigatorio_ausente(record, campo):
    with pytest.raises(ValueError, match=campo):
        render({**record, campo: "  "}, ISSUER)


@pytest.mark.parametrize("record", [CERTIFICADO, DECLARACAO])
def test_imagens_do_emissor(record, tmp_path):
    from PIL import Image

    img = tmp_path / "img.png"
    Image.new("RGBA", (40, 20), (255, 255, 255, 0)).save(img)
    issuer = {**ISSUER, "logo": str(img), "logo_branco": str(img), "assinatura": str(img)}
    assert render(record, issuer).startswith(b"%PDF")


@pytest.mark.parametrize("raw", ["2026-03-15", "15/03/2026"])
def test_parse_date_formatos(raw):
    assert format_date_pt(parse_date(raw)) == "15 de março de 2026"
