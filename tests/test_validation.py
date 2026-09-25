import io
from urllib.parse import urlsplit

import pytest
from pypdf import PdfReader

import app as app_module
from src.engine import render
from src.validation import ID_PATTERN, clean_id, conteudo_do_curso, find, new_id, public_view
from tests.test_engine import CERTIFICADO, CONTEUDO, DECLARACAO, ISSUER

# Aba "Conteudos" como o gspread devolve: uma linha por item.
CONTEUDO_ROWS = [{"curso": "Inglês", "semestre": s, "item": i} for s, i in CONTEUDO] + [
    {"curso": "Espanhol", "semestre": "1º semestre", "item": "Tópico de outro curso"},
    {"curso": "Inglês", "semestre": "1º semestre", "item": "  "},
]

RECORDS = [
    CERTIFICADO,
    DECLARACAO,
    {**CERTIFICADO, "id": "RevogadoXXXX", "status": "revogado"},
]


# --- ID ---

def test_novo_id_formato_unico_e_nao_sequencial():
    ids = [new_id() for _ in range(1000)]
    assert all(ID_PATTERN.fullmatch(i) for i in ids)
    assert len(set(ids)) == len(ids)
    assert ids != sorted(ids)


@pytest.mark.parametrize("raw", ["", "curto", "k7Qm2xPz9aBc'--", "../../etc/pa", "k7Qm2xPz9aB c", None])
def test_clean_id_rejeita_formato_invalido(raw):
    assert clean_id(raw) is None


# --- Consulta ---

def test_id_existente_retorna_dados_publicos():
    view = public_view(find(RECORDS, "k7Qm2xPz9aBc"))
    assert view == {
        "tipo": "Certificado de conclusão de curso",
        "nome": "Maria Exemplo da Silva",
        "curso": "Inglês",
        "carga_horaria": "40",
        "data_emissao": "15 de março de 2026",
        "valido": True,
    }


def test_declaracao_nao_expoe_dados_pessoais():
    view = public_view(find(RECORDS, DECLARACAO["id"]))
    assert view["valido"] and view["tipo"] == "Declaração de matrícula"
    exposed = " ".join(str(v) for v in view.values())
    for secret in (DECLARACAO["cpf"], DECLARACAO["rg"], DECLARACAO["endereco"]):
        assert secret not in exposed


def test_id_inexistente_retorna_none_sem_excecao():
    assert find(RECORDS, "naoExiste123") is None
    assert find(RECORDS, "formato inválido") is None


def test_conteudo_do_curso_filtra_e_mantem_ordem():
    assert conteudo_do_curso(CONTEUDO_ROWS, " inglês ") == CONTEUDO
    assert conteudo_do_curso(CONTEUDO_ROWS, "Alemão") == []


def test_status_diferente_de_ativo_nao_e_valido():
    assert public_view(find(RECORDS, "RevogadoXXXX"))["valido"] is False


# --- Rota /validar ---

@pytest.fixture
def client():
    app_module.app.config["LOAD_RECORDS"] = lambda: RECORDS
    app_module.app.config["LOAD_CONTEUDOS"] = lambda: CONTEUDO_ROWS
    app_module._hits.clear()
    return app_module.app.test_client()


def test_rota_documento_valido(client):
    r = client.get("/validar?id=k7Qm2xPz9aBc")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Documento válido" in body and "Maria Exemplo da Silva" in body


def test_rota_declaracao_valida_sem_dados_pessoais(client):
    body = client.get(f"/validar?id={DECLARACAO['id']}").get_data(as_text=True)
    assert "Documento válido" in body and "João Exemplo Souza" in body
    for secret in (DECLARACAO["cpf"], DECLARACAO["rg"], "Rua Fictícia"):
        assert secret not in body


def test_rota_nao_encontrado(client):
    r = client.get("/validar?id=naoExiste123")
    assert r.status_code == 404 and "não encontrado" in r.get_data(as_text=True)


def test_rota_id_malformado_nao_consulta_planilha(client):
    def boom():
        raise AssertionError("não deveria consultar a planilha")

    app_module.app.config["LOAD_RECORDS"] = boom
    r = client.get("/validar?id=<script>alert(1)</script>")
    assert r.status_code == 404 and "<script>" not in r.get_data(as_text=True)


def test_rota_revogado(client):
    r = client.get("/validar?id=RevogadoXXXX")
    assert r.status_code == 200 and "não é mais válido" in r.get_data(as_text=True)


def test_rate_limit(client):
    codes = [client.get("/validar?id=naoExiste123").status_code for _ in range(app_module.RATE_LIMIT + 1)]
    assert codes[-1] == 429 and 429 not in codes[:-1]


# --- Fluxo completo ---

def test_integracao_registro_pdf_qr_pagina(client):
    """Registro -> PDF com QR -> link do QR -> página de validação."""
    pdf = render(CERTIFICADO, ISSUER, "https://exemplo.com/validar")
    page = PdfReader(io.BytesIO(pdf)).pages[0]
    url = next(a.get_object()["/A"]["/URI"] for a in page["/Annots"])
    assert url == "https://exemplo.com/validar?id=k7Qm2xPz9aBc"

    parts = urlsplit(url)
    body = client.get(f"{parts.path}?{parts.query}").get_data(as_text=True)
    assert "Documento válido" in body
    assert "Maria Exemplo da Silva" in body and "Inglês" in body and "15 de março de 2026" in body


# --- Comandos de emissão ---

def test_cli_novo_id(client):
    out = app_module.app.test_cli_runner().invoke(args=["novo-id", "-n", "3"]).output.split()
    assert len(out) == 3 and all(ID_PATTERN.fullmatch(i) for i in out)


def test_cli_pdf(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for k, v in ISSUER.items():
        monkeypatch.setenv(f"ISSUER_{k.upper()}", v)
    runner = app_module.app.test_cli_runner()
    assert runner.invoke(args=["pdf", "k7Qm2xPz9aBc"]).exit_code == 0
    pdf = (tmp_path / "k7Qm2xPz9aBc.pdf").read_bytes()
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 2  # conteúdo veio da aba "Conteudos"
    assert runner.invoke(args=["pdf", "naoExiste123"]).exit_code != 0
