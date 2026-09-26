import base64
import io
import threading
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


@pytest.mark.parametrize("raw", ["", "curto", "k7Qm2xPz9aBc'--", "../../etc/pa", "k7Qm2xPz9aB c", "-7Qm2xPz9aBc", None])
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

BASE = "https://exemplo.com/validar"


@pytest.fixture
def client(monkeypatch):
    app_module.app.config["LOAD_RECORDS"] = lambda: RECORDS
    app_module.app.config["LOAD_CONTEUDOS"] = lambda: CONTEUDO_ROWS
    app_module._hits.clear()
    app_module._auth_fails.clear()
    app_module._cache.clear()
    monkeypatch.setattr(app_module, "_purged_at", 0.0)
    monkeypatch.setenv("VALIDATION_BASE_URL", BASE)
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


def test_cli_pdf_sem_conteudo_nao_consulta_aba_de_conteudos(client, tmp_path, monkeypatch):
    def boom():
        raise AssertionError("não deveria consultar os conteúdos")

    app_module.app.config["LOAD_CONTEUDOS"] = boom
    monkeypatch.chdir(tmp_path)
    assert app_module.app.test_cli_runner().invoke(args=["pdf", DECLARACAO["id"]]).exit_code == 0


def test_cli_pdf(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for k, v in ISSUER.items():
        monkeypatch.setenv(f"ISSUER_{k.upper()}", v)
    runner = app_module.app.test_cli_runner()
    assert runner.invoke(args=["pdf", "k7Qm2xPz9aBc"]).exit_code == 0
    pdf = (tmp_path / "k7Qm2xPz9aBc.pdf").read_bytes()
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 2  # conteúdo veio da aba "Conteudos"
    assert runner.invoke(args=["pdf", "naoExiste123"]).exit_code != 0


# --- Emissão (/emitir) ---

SENHA = "senha-de-teste"


def auth(senha=SENHA):
    return {"Authorization": "Basic " + base64.b64encode(f"escola:{senha}".encode()).decode()}


@pytest.fixture
def admin(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", SENHA)
    for k, v in ISSUER.items():
        monkeypatch.setenv(f"ISSUER_{k.upper()}", v)
    return client


def test_emitir_sem_senha_configurada_nao_existe(client, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    assert client.get("/emitir", headers=auth()).status_code == 404


def test_emitir_pede_senha(admin):
    r = admin.get("/emitir")
    assert r.status_code == 401 and "Basic" in r.headers["WWW-Authenticate"]
    assert admin.get("/emitir", headers=auth("errada")).status_code == 401


def test_emitir_lista_documentos_e_ids_novos(admin):
    r = admin.get("/emitir", headers=auth())
    body = r.get_data(as_text=True)
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"
    assert "Maria Exemplo da Silva" in body and "João Exemplo Souza" in body
    assert "/emitir/k7Qm2xPz9aBc.pdf" in body
    import re
    novos = re.findall(r"<code>([A-Za-z0-9]{12})</code>", body)
    assert len(novos) == 5 and not set(novos) & {r["id"] for r in RECORDS}
    assert DECLARACAO["cpf"] not in body  # a lista não mostra dados pessoais


@pytest.mark.parametrize("record, paginas", [(CERTIFICADO, 2), (DECLARACAO, 1)])
def test_emitir_baixa_pdf(admin, record, paginas):
    r = admin.get(f"/emitir/{record['id']}.pdf", headers=auth())
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    assert "attachment" in r.headers["Content-Disposition"]
    assert len(PdfReader(io.BytesIO(r.data)).pages) == paginas


def test_emitir_pdf_exige_senha(admin):
    assert admin.get("/emitir/k7Qm2xPz9aBc.pdf").status_code == 401


def test_emitir_pdf_inexistente(admin):
    assert admin.get("/emitir/naoExiste123.pdf", headers=auth()).status_code == 404


def test_emitir_pdf_com_erro_na_planilha_mostra_motivo(admin):
    app_module.app.config["LOAD_CONTEUDOS"] = lambda: []  # curso sem conteúdo cadastrado
    r = admin.get("/emitir/k7Qm2xPz9aBc.pdf", headers=auth())
    assert r.status_code == 422 and "conteudo" in r.get_data(as_text=True)


def test_atras_de_proxy_rate_limit_usa_ip_real(monkeypatch):
    import importlib

    monkeypatch.setenv("TRUST_PROXY", "1")
    mod = importlib.reload(app_module)
    try:
        mod.app.config["LOAD_RECORDS"] = lambda: RECORDS
        c = mod.app.test_client()
        for _ in range(mod.RATE_LIMIT):
            c.get("/validar?id=naoExiste123", headers={"X-Forwarded-For": "1.1.1.1"})
        # outro visitante (IP real diferente) não é afetado pelo limite do primeiro
        assert c.get("/validar?id=naoExiste123", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 404
        assert c.get("/validar?id=naoExiste123", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
    finally:
        monkeypatch.delenv("TRUST_PROXY")
        importlib.reload(app_module)


# --- LinkedIn ---

def test_linkedin_url_parametros_e_codificacao():
    from urllib.parse import parse_qs, urlsplit

    from src.linkedin import linkedin_url

    url = linkedin_url(CERTIFICADO, "https://exemplo.com/validar?id=k7Qm2xPz9aBc", "Escola Exemplo & Cia")
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://www.linkedin.com/profile/add"
    assert " " not in url and "&Cia" not in url  # tudo codificado
    q = {k: v[0] for k, v in parse_qs(parts.query).items()}
    assert q == {
        "startTask": "CERTIFICATION_NAME",
        "name": "Certificado de conclusão de curso — Inglês",
        "organizationName": "Escola Exemplo & Cia",
        "issueYear": "2026",
        "issueMonth": "3",
        "certUrl": "https://exemplo.com/validar?id=k7Qm2xPz9aBc",
        "certId": "k7Qm2xPz9aBc",
    }


def test_linkedin_usa_id_da_organizacao_quando_existe():
    from urllib.parse import parse_qs, urlsplit

    from src.linkedin import linkedin_url

    q = parse_qs(urlsplit(linkedin_url(CERTIFICADO, "https://x", "Escola", "12345")).query)
    assert q["organizationId"] == ["12345"] and "organizationName" not in q


def test_linkedin_nao_se_aplica_a_declaracao():
    from src.linkedin import linkedin_url

    assert linkedin_url(DECLARACAO, "https://x", "Escola") is None


def test_pagina_mostra_linkedin_so_para_certificado_valido(client):
    assert "Adicionar ao LinkedIn" in client.get("/validar?id=k7Qm2xPz9aBc").get_data(as_text=True)
    assert "Adicionar ao LinkedIn" not in client.get(f"/validar?id={DECLARACAO['id']}").get_data(as_text=True)
    assert "Adicionar ao LinkedIn" not in client.get("/validar?id=RevogadoXXXX").get_data(as_text=True)


# === Segurança e robustez (auditoria) ===


@pytest.fixture
def clock(monkeypatch):
    """Relógio controlado para as janelas do rate limit e o TTL do cache."""
    now = [1000.0]
    monkeypatch.setattr(app_module.time, "monotonic", lambda: now[0])
    return now


def csp_ok(r):
    csp = r.headers.get("Content-Security-Policy", "")
    return (
        "default-src 'none'" in csp and "frame-ancestors 'none'" in csp and "base-uri 'none'" in csp
        and r.headers.get("X-Content-Type-Options") == "nosniff" and r.headers.get("Referrer-Policy") == "no-referrer"
    )


# --- R1: senha de /emitir ---

def test_senha_errada_bloqueia_durante_a_janela(admin, clock):
    for _ in range(app_module.RATE_LIMIT):
        assert admin.get("/emitir", headers=auth("errada")).status_code == 401
    r = admin.get("/emitir", headers=auth("outra"))
    assert r.status_code == 429 and r.headers["Retry-After"] == str(app_module.WINDOW)
    assert "WWW-Authenticate" not in r.headers  # não convida a tentar de novo
    clock[0] += app_module.WINDOW - 1
    assert admin.get("/emitir", headers=auth("mais uma")).status_code == 429


def test_senha_certa_nao_contorna_o_bloqueio(admin, clock):
    for _ in range(app_module.RATE_LIMIT):
        admin.get("/emitir", headers=auth("errada"))
    assert admin.get("/emitir", headers=auth()).status_code == 429
    assert admin.get("/emitir/k7Qm2xPz9aBc.pdf", headers=auth()).status_code == 429


def test_bloqueio_expira_depois_da_janela(admin, clock):
    for _ in range(app_module.RATE_LIMIT):
        admin.get("/emitir", headers=auth("errada"))
    clock[0] += app_module.WINDOW - 1
    assert admin.get("/emitir", headers=auth()).status_code == 429  # ainda na janela
    clock[0] += 2
    assert admin.get("/emitir", headers=auth()).status_code == 200  # expirou sozinho


def test_bloqueio_de_senha_e_por_cliente(admin, clock):
    for _ in range(app_module.RATE_LIMIT):
        admin.get("/emitir", headers=auth("errada"), environ_base={"REMOTE_ADDR": "198.51.100.1"})
    bloqueado = admin.get("/emitir", headers=auth(), environ_base={"REMOTE_ADDR": "198.51.100.1"})
    outro = admin.get("/emitir", headers=auth(), environ_base={"REMOTE_ADDR": "198.51.100.2"})
    assert bloqueado.status_code == 429 and outro.status_code == 200


def test_sem_admin_password_nada_abre_a_area_nem_conta_tentativa(client, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    for senha in [""] * (app_module.RATE_LIMIT + 2) + ["qualquer"]:
        r = client.get("/emitir", headers=auth(senha))
        assert r.status_code == 404 and "Maria" not in r.get_data(as_text=True)
    assert client.get("/emitir/k7Qm2xPz9aBc.pdf", headers=auth("")).status_code == 404
    assert not app_module._auth_fails


def test_pedido_sem_senha_e_senha_certa_nao_consomem_tentativas(admin, clock):
    for _ in range(app_module.RATE_LIMIT * 2):
        assert admin.get("/emitir").status_code == 401  # navegador pedindo a senha
        assert admin.get("/emitir", headers=auth()).status_code == 200


def rajada_de_senhas(monkeypatch, senhas):
    """Dispara uma requisição por thread e segura cada uma DENTRO da comparação
    de senha até todas estarem lá ou já terem respondido. A liberação depende de
    uma condição explícita, não de tempo: o resultado é determinístico.
    Devolve (status de cada requisição, quantas senhas foram comparadas)."""
    real = app_module.hmac.compare_digest
    cond, portao = threading.Condition(), threading.Event()
    estado = {"comparando": 0, "respondidas": 0}

    def compare(a, b):
        with cond:
            estado["comparando"] += 1
            cond.notify_all()
        assert portao.wait(10), "portão nunca abriu"  # só proteção contra travar a suíte
        return real(a, b)

    monkeypatch.setattr(app_module.hmac, "compare_digest", compare)
    codes = [None] * len(senhas)

    def pedido(i, senha):
        try:
            codes[i] = app_module.app.test_client().get("/emitir", headers=auth(senha)).status_code
        finally:
            with cond:
                estado["respondidas"] += 1
                cond.notify_all()

    threads = [threading.Thread(target=pedido, args=(i, s)) for i, s in enumerate(senhas)]
    for t in threads:
        t.start()
    with cond:  # todas presas na comparação ou já respondidas (com o portão fechado)
        assert cond.wait_for(lambda: estado["comparando"] + estado["respondidas"] == len(senhas), timeout=10)
        comparadas = estado["comparando"]
    portao.set()
    for t in threads:
        t.join()
    monkeypatch.setattr(app_module.hmac, "compare_digest", real)
    return codes, comparadas


def test_senhas_erradas_simultaneas_nao_passam_do_limite(admin, clock, monkeypatch):
    extra = 5
    codes, comparadas = rajada_de_senhas(monkeypatch, ["errada"] * (app_module.RATE_LIMIT + extra))
    assert comparadas == app_module.RATE_LIMIT  # nenhuma senha testada além do limite
    assert codes.count(401) == app_module.RATE_LIMIT and codes.count(429) == extra
    assert len(app_module._auth_fails["127.0.0.1"]) == app_module.RATE_LIMIT
    assert admin.get("/emitir", headers=auth()).status_code == 429  # senha certa no bloqueio
    clock[0] += app_module.WINDOW + 1
    assert admin.get("/emitir", headers=auth()).status_code == 200  # expirou


def test_senhas_certas_simultaneas_nao_consomem_tentativas(admin, clock, monkeypatch):
    codes, comparadas = rajada_de_senhas(monkeypatch, [SENHA] * 8)
    assert codes == [200] * 8 and comparadas == 8
    assert not app_module._auth_fails  # a vaga reservada foi devolvida
    for _ in range(app_module.RATE_LIMIT - 1):  # o limite inteiro continua disponível
        admin.get("/emitir", headers=auth("errada"))
    assert admin.get("/emitir", headers=auth("errada")).status_code == 401


def test_limites_de_senha_e_de_validacao_sao_separados(admin, clock):
    for _ in range(app_module.RATE_LIMIT):
        admin.get("/validar?id=naoExiste123")
    assert admin.get("/validar?id=naoExiste123").status_code == 429
    assert admin.get("/emitir", headers=auth()).status_code == 200
    app_module._hits.clear()
    for _ in range(app_module.RATE_LIMIT):
        admin.get("/emitir", headers=auth("errada"))
    assert admin.get("/validar?id=k7Qm2xPz9aBc").status_code == 200


@pytest.mark.parametrize("header", [
    "Bearer abc",
    "Basic !!!nao-e-base64",
    "Basic " + base64.b64encode(b"sem-dois-pontos").decode(),
    "Basic ",
    "Digest username=x",
])
def test_authorization_malformado_da_401(admin, header):
    r = admin.get("/emitir", headers={"Authorization": header})
    assert r.status_code == 401 and "Maria" not in r.get_data(as_text=True)


def test_usuario_e_ignorado_so_a_senha_conta(admin):
    h = {"Authorization": "Basic " + base64.b64encode(f"qualquer:{SENHA}".encode()).decode()}
    assert admin.get("/emitir", headers=h).status_code == 200


@pytest.mark.parametrize("method, path", [
    ("GET", "/emitir/"),
    ("GET", "/EMITIR"),
    ("GET", "/emitir/k7Qm2xPz9aBc"),
    ("POST", "/emitir"),
    ("HEAD", "/emitir"),
    ("GET", "/emitir/k7Qm2xPz9aBc.pdf"),
    ("GET", "/emitir/..%2F..%2Fetc.pdf"),
    ("GET", "/emitir/<script>.pdf"),
])
def test_rotas_de_emissao_sem_senha_nao_entregam_nada(admin, method, path):
    r = admin.open(path, method=method)
    assert r.status_code in (401, 404, 405)
    assert r.mimetype != "application/pdf" and "Maria" not in r.get_data(as_text=True)


@pytest.mark.parametrize("path", ["/emitir/curto.pdf", "/emitir/k7Qm2xPz9aB%27.pdf", "/emitir/<script>.pdf"])
def test_pdf_com_id_malformado_da_404(admin, path):
    assert admin.get(path, headers=auth()).status_code == 404


# --- R2: falha da planilha e cache ---

def falha_do_google():
    raise RuntimeError("APIError: [429] Quota exceeded for quota metric 'Read requests' sheet=SEGREDO123")


@pytest.mark.parametrize("path, carregador", [
    ("/validar?id=k7Qm2xPz9aBc", "LOAD_RECORDS"),
    ("/emitir", "LOAD_RECORDS"),
    ("/emitir/k7Qm2xPz9aBc.pdf", "LOAD_RECORDS"),
    ("/emitir/k7Qm2xPz9aBc.pdf", "LOAD_CONTEUDOS"),
])
def test_falha_da_planilha_da_503_generico(admin, path, carregador):
    app_module.app.config[carregador] = falha_do_google
    r = admin.get(path, headers=auth())
    body = r.get_data(as_text=True)
    assert r.status_code == 503 and "temporariamente indisponível" in body
    assert r.headers["Retry-After"] == str(app_module.WINDOW)
    for vazamento in ("Quota", "SEGREDO123", "Traceback", "RuntimeError", "APIError", "LOAD_"):
        assert vazamento not in body
    assert csp_ok(r)


def test_erro_inesperado_da_500_generico(client, monkeypatch):
    def quebra(record):
        raise KeyError("detalhe interno SEGREDO123")

    monkeypatch.setattr(app_module, "public_view", quebra)
    r = client.get("/validar?id=k7Qm2xPz9aBc")
    body = r.get_data(as_text=True)
    assert r.status_code == 500 and "SEGREDO123" not in body and "Traceback" not in body
    assert csp_ok(r)


def test_cache_evita_ler_a_planilha_a_cada_consulta(client, clock):
    leituras = []
    app_module.app.config["LOAD_RECORDS"] = lambda: leituras.append(1) or RECORDS
    for _ in range(5):
        assert client.get("/validar?id=k7Qm2xPz9aBc").status_code == 200
    assert len(leituras) == 1


def test_revogacao_aparece_no_maximo_depois_do_ttl(client, clock):
    planilha = [dict(CERTIFICADO)]
    app_module.app.config["LOAD_RECORDS"] = lambda: [dict(r) for r in planilha]
    assert "Documento válido" in client.get("/validar?id=k7Qm2xPz9aBc").get_data(as_text=True)
    planilha[0]["status"] = "revogado"
    clock[0] += app_module.CACHE_TTL - 1
    assert "Documento válido" in client.get("/validar?id=k7Qm2xPz9aBc").get_data(as_text=True)
    clock[0] += 2
    assert "não é mais válido" in client.get("/validar?id=k7Qm2xPz9aBc").get_data(as_text=True)


def test_falha_da_planilha_nao_fica_em_cache(client, clock):
    app_module.app.config["LOAD_RECORDS"] = falha_do_google
    assert client.get("/validar?id=k7Qm2xPz9aBc").status_code == 503
    app_module.app.config["LOAD_RECORDS"] = lambda: RECORDS
    assert client.get("/validar?id=k7Qm2xPz9aBc").status_code == 200


def test_emissao_le_a_planilha_sem_cache(admin, clock):
    leituras = []
    app_module.app.config["LOAD_RECORDS"] = lambda: leituras.append(1) or RECORDS
    admin.get("/emitir", headers=auth())
    admin.get("/emitir", headers=auth())
    admin.get("/validar?id=k7Qm2xPz9aBc")
    admin.get("/validar?id=k7Qm2xPz9aBc")
    assert len(leituras) == 3  # 2 da emissão + 1 da validação (cacheada)


# --- R3: IDs duplicados ---

@pytest.mark.parametrize("status_a, status_b", [
    ("ativo", "ativo"), ("ativo", "revogado"), ("revogado", "ativo"), ("revogado", "revogado"),
])
def test_id_duplicado_nao_seleciona_nenhuma_linha(client, status_a, status_b):
    linhas = [
        {**CERTIFICADO, "nome": "Primeira Linha", "curso": "Alemão", "status": status_a},
        {**CERTIFICADO, "nome": "Segunda Linha", "curso": "Italiano", "status": status_b},
        DECLARACAO,
    ]
    assert find(linhas, CERTIFICADO["id"]) is None
    app_module.app.config["LOAD_RECORDS"] = lambda: linhas
    r = client.get(f"/validar?id={CERTIFICADO['id']}")
    body = r.get_data(as_text=True)
    assert r.status_code == 404 and "não encontrado" in body
    for dado in ("Primeira Linha", "Segunda Linha", "Alemão", "Italiano", "Documento válido", "LinkedIn"):
        assert dado not in body


def test_id_duplicado_com_espacos_tambem_e_ambiguo():
    linhas = [CERTIFICADO, {**CERTIFICADO, "id": f"  {CERTIFICADO['id']} "}]
    assert find(linhas, CERTIFICADO["id"]) is None


def test_emissao_sinaliza_id_duplicado_e_nao_gera_pdf(admin):
    linhas = [CERTIFICADO, {**CERTIFICADO, "nome": "Outra Pessoa"}, DECLARACAO]
    app_module.app.config["LOAD_RECORDS"] = lambda: linhas
    body = admin.get("/emitir", headers=auth()).get_data(as_text=True)
    assert body.count("ID duplicado") == 2
    assert f"/emitir/{CERTIFICADO['id']}.pdf" not in body
    assert f"/emitir/{DECLARACAO['id']}.pdf" in body
    assert admin.get(f"/emitir/{CERTIFICADO['id']}.pdf", headers=auth()).status_code == 404


# --- R4: memória do rate limit e IPv6 ---

@pytest.mark.parametrize("ip, chave", [
    ("203.0.113.5", "203.0.113.5"),
    ("::ffff:203.0.113.5", "203.0.113.5"),
    ("2001:db8:1:2::1", "2001:db8:1:2::/64"),
    ("2001:db8:1:2:ffff:ffff:ffff:ffff", "2001:db8:1:2::/64"),
    ("2001:db8:1:3::1", "2001:db8:1:3::/64"),
    ("nao-e-ip", "nao-e-ip"),
    (None, "None"),
])
def test_chave_do_cliente(ip, chave):
    assert app_module.client_key(ip) == chave


def test_ipv6_do_mesmo_bloco_64_divide_o_limite(client, clock):
    for i in range(app_module.RATE_LIMIT):
        client.get("/validar?id=naoExiste123", environ_base={"REMOTE_ADDR": f"2001:db8:1:2::{i + 1:x}"})
    mesmo_bloco = client.get("/validar?id=naoExiste123", environ_base={"REMOTE_ADDR": "2001:db8:1:2::ffff"})
    outro_bloco = client.get("/validar?id=naoExiste123", environ_base={"REMOTE_ADDR": "2001:db8:1:3::1"})
    assert mesmo_bloco.status_code == 429 and outro_bloco.status_code == 404


def test_entradas_expiradas_sao_removidas(client, clock):
    for i in range(500):
        client.get("/validar?id=naoExiste123", environ_base={"REMOTE_ADDR": f"10.0.{i // 250}.{i % 250}"})
    assert len(app_module._hits) == 500
    clock[0] += app_module.WINDOW + 1
    client.get("/validar?id=naoExiste123", environ_base={"REMOTE_ADDR": "10.9.9.9"})
    assert list(app_module._hits) == ["10.9.9.9"]


def test_memoria_nao_cresce_com_trafego_continuo(client, clock):
    for rodada in range(5):
        for i in range(200):
            client.get("/validar?id=naoExiste123", environ_base={"REMOTE_ADDR": f"10.{rodada}.0.{i}"})
        clock[0] += app_module.WINDOW + 1
    assert len(app_module._hits) <= 200


def test_consultas_malformadas_tambem_contam_no_limite(client):
    for i in range(app_module.RATE_LIMIT):
        client.get(f"/validar?id=lixo{i}")
    assert client.get("/validar?id=k7Qm2xPz9aBc").status_code == 429


# --- R5: X-Forwarded-For ---

def test_sem_trust_proxy_x_forwarded_for_e_ignorado(client, monkeypatch):
    monkeypatch.delenv("TRUST_PROXY", raising=False)
    codes = [
        client.get("/validar?id=naoExiste123", headers={"X-Forwarded-For": f"198.51.100.{i}"}).status_code
        for i in range(app_module.RATE_LIMIT + 1)
    ]
    assert codes[-1] == 429  # trocar o cabeçalho não cria um cliente novo
    assert list(app_module._hits) == ["127.0.0.1"]


def test_sem_trust_proxy_x_forwarded_for_nao_contorna_bloqueio_de_senha(admin):
    for i in range(app_module.RATE_LIMIT):
        admin.get("/emitir", headers={**auth("errada"), "X-Forwarded-For": f"198.51.100.{i}"})
    r = admin.get("/emitir", headers={**auth(), "X-Forwarded-For": "198.51.100.200"})
    assert r.status_code == 429


# --- R6: VALIDATION_BASE_URL ---

def qr_url(pdf):
    return next(a.get_object()["/A"]["/URI"] for a in PdfReader(io.BytesIO(pdf)).pages[0]["/Annots"])


def test_pdf_emitido_tem_qr_com_a_url_configurada(admin):
    r = admin.get("/emitir/k7Qm2xPz9aBc.pdf", headers={**auth(), "Host": "atacante.example"})
    assert r.status_code == 200 and qr_url(r.data) == f"{BASE}?id=k7Qm2xPz9aBc"


def test_sem_validation_base_url_a_emissao_falha_explicitamente(admin, monkeypatch):
    monkeypatch.delenv("VALIDATION_BASE_URL")
    r = admin.get("/emitir/k7Qm2xPz9aBc.pdf", headers=auth())
    assert r.status_code == 422 and r.mimetype != "application/pdf"
    assert "VALIDATION_BASE_URL" in r.get_data(as_text=True)


def test_sem_validation_base_url_o_comando_pdf_falha(client, monkeypatch, tmp_path):
    monkeypatch.delenv("VALIDATION_BASE_URL")
    monkeypatch.chdir(tmp_path)
    result = app_module.app.test_cli_runner().invoke(args=["pdf", DECLARACAO["id"]])
    assert result.exit_code != 0 and "VALIDATION_BASE_URL" in result.output
    assert not list(tmp_path.iterdir())  # nenhum PDF sem QR foi gravado


def test_link_do_linkedin_ignora_host_malicioso(client):
    body = client.get("/validar?id=k7Qm2xPz9aBc", headers={"Host": "atacante.example"}).get_data(as_text=True)
    assert "atacante.example" not in body
    assert "certUrl=https%3A%2F%2Fexemplo.com%2Fvalidar%3Fid%3Dk7Qm2xPz9aBc" in body


def test_sem_validation_base_url_valida_mas_sem_linkedin(client, monkeypatch):
    monkeypatch.delenv("VALIDATION_BASE_URL")
    body = client.get("/validar?id=k7Qm2xPz9aBc", headers={"Host": "atacante.example"}).get_data(as_text=True)
    assert "Documento válido" in body
    assert "Adicionar ao LinkedIn" not in body and "atacante.example" not in body


# --- R7: nome do arquivo baixado ---

@pytest.mark.parametrize("entrada, esperado", [
    ("Declaração de matrícula - Ana Souza.pdf", "Declaração de matrícula - Ana Souza.pdf"),
    ("Ana\r\nSet-Cookie: x=1.pdf", "AnaSet-Cookie: x=1.pdf"),
    ("Ana\tSouza\x00\x1b.pdf", "AnaSouza.pdf"),
    ("Ana ‮gpj.pdf", "Ana gpj.pdf"),  # inversão de direção (RLO)
    ('../../etc/"passwd".pdf', "....etcpasswd.pdf"),
    ("\r\n", "documento.pdf"),
])
def test_download_name(entrada, esperado):
    assert app_module.download_name(entrada) == esperado


def test_nome_com_quebra_de_linha_nao_derruba_o_download(admin):
    linhas = [{**DECLARACAO, "nome": "Ana\r\nSet-Cookie: x=1"}]
    app_module.app.config["LOAD_RECORDS"] = lambda: linhas
    r = admin.get(f"/emitir/{DECLARACAO['id']}.pdf", headers=auth())
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    assert "\n" not in r.headers["Content-Disposition"] and "Set-Cookie" not in r.headers


# --- R8: cabeçalhos em todas as respostas ---

@pytest.mark.parametrize("path, esperado", [
    ("/validar", 200),
    ("/validar?id=k7Qm2xPz9aBc", 200),
    ("/validar?id=lixo", 404),
    ("/rota-que-nao-existe", 404),
    ("/emitir", 401),
])
def test_cabecalhos_de_seguranca(admin, path, esperado):
    r = admin.get(path)
    assert r.status_code == esperado and csp_ok(r)


def test_cabecalhos_de_seguranca_em_429_e_na_emissao(admin):
    for _ in range(app_module.RATE_LIMIT):
        admin.get("/validar?id=naoExiste123")
    assert csp_ok(admin.get("/validar?id=naoExiste123"))
    r = admin.get("/emitir", headers=auth())
    assert csp_ok(r) and r.headers["Cache-Control"] == "no-store"
    r = admin.get("/emitir/k7Qm2xPz9aBc.pdf", headers=auth())
    assert csp_ok(r) and r.headers["Cache-Control"] == "no-store"


def test_cabecalhos_de_seguranca_sem_area_de_emissao(client, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    r = client.get("/emitir")
    assert r.status_code == 404 and csp_ok(r)


# --- Dados vindos da planilha e da URL ---

XSS = '<script>alert(1)</script>"><img src=x onerror=alert(1)>'


def test_xss_vindo_da_planilha_e_escapado_na_validacao(client):
    linhas = [{**CERTIFICADO, "nome": XSS, "curso": XSS, "carga_horaria": XSS}]
    app_module.app.config["LOAD_RECORDS"] = lambda: linhas
    body = client.get("/validar?id=k7Qm2xPz9aBc").get_data(as_text=True)
    assert "Documento válido" in body
    assert "<script>alert" not in body and "<img src=x" not in body
    assert "&lt;script&gt;" in body


def test_xss_vindo_da_planilha_e_escapado_na_emissao(admin):
    linhas = [{**CERTIFICADO, "nome": XSS, "curso": XSS, "tipo_documento": XSS, "status": XSS}]
    app_module.app.config["LOAD_RECORDS"] = lambda: linhas
    body = admin.get("/emitir", headers=auth()).get_data(as_text=True)
    assert "<script>alert" not in body and "<img src=x" not in body


def test_revogado_nao_mostra_dados(client):
    body = client.get("/validar?id=RevogadoXXXX").get_data(as_text=True)
    assert "não é mais válido" in body
    for dado in ("Maria Exemplo da Silva", "Inglês", "40 horas", "LinkedIn"):
        assert dado not in body


def test_tipo_desconhecido_nao_valida_nem_quebra(client):
    linhas = [{**CERTIFICADO, "tipo_documento": "diploma"}]
    app_module.app.config["LOAD_RECORDS"] = lambda: linhas
    r = client.get("/validar?id=k7Qm2xPz9aBc")
    body = r.get_data(as_text=True)
    assert r.status_code == 200 and "não é mais válido" in body
    assert "Documento válido" not in body and "Maria Exemplo da Silva" not in body


def test_inexistente_e_malformado_tem_a_mesma_resposta(client):
    inexistente = client.get("/validar?id=naoExiste123")
    malformado = client.get("/validar?id=%27%20OR%201%3D1%20--")
    assert inexistente.status_code == malformado.status_code == 404
    # A única diferença é o ID bem formado voltar preenchido no campo de busca.
    assert inexistente.get_data(as_text=True).replace("naoExiste123", "") == malformado.get_data(as_text=True)


@pytest.mark.parametrize("raw", ["k7Qm2xPz9aBc" * 1000, "K7QM2XPZ9ABC", "ｋ7Qm2xPz9aBc", "k7Qm2xPz9aB٣", "k7Qm2xPz9aBc\n"],
                         ids=["12-mil-caracteres", "maiusculas", "largura-total", "digito-arabe", "quebra-no-fim"])
def test_ids_inesperados_nao_encontram_nem_refletem(client, raw):
    app_module.app.config["LOAD_RECORDS"] = lambda: RECORDS
    r = client.get("/validar", query_string={"id": raw})
    body = r.get_data(as_text=True)
    if raw.strip() == CERTIFICADO["id"]:  # espaço/quebra nas pontas é aparado, como na planilha
        assert r.status_code == 200
    else:
        assert r.status_code == 404 and "não encontrado" in body
        # Só um ID bem formado volta preenchido no campo de busca (escapado pelo Jinja).
        assert (raw in body) == (clean_id(raw) is not None)


def test_parametros_extras_nao_mudam_o_resultado(client):
    r = client.get("/validar?id=RevogadoXXXX&status=ativo&valido=1&tipo=certificado_curso")
    assert "não é mais válido" in r.get_data(as_text=True)
    # id repetido: vale o primeiro, como qualquer consulta normal
    r = client.get("/validar?id=RevogadoXXXX&id=k7Qm2xPz9aBc")
    assert "não é mais válido" in r.get_data(as_text=True)


def test_qr_e_pdf_da_declaracao_sem_dados_privados(admin):
    r = admin.get(f"/emitir/{DECLARACAO['id']}.pdf", headers=auth())
    url = qr_url(r.data)
    assert url == f"{BASE}?id={DECLARACAO['id']}"
    metadados = " ".join(str(v) for v in (PdfReader(io.BytesIO(r.data)).metadata or {}).values())
    for privado in (DECLARACAO["cpf"], DECLARACAO["rg"], DECLARACAO["endereco"], DECLARACAO["nome"]):
        assert privado not in url and privado not in metadados
