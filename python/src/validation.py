"""Geração e consulta de IDs de validação."""
import os
import re
import secrets
import string

from .engine import format_date_pt, parse_date
from .templates import TEMPLATES

# 12 letras/dígitos = ~71 bits aleatórios: impossível varrer por tentativa.
# Sem "-" ou "_": no Sheets, um valor começando com "-" vira fórmula.
ID_ALPHABET = string.ascii_letters + string.digits
ID_PATTERN = re.compile(r"[A-Za-z0-9]{12}")


def new_id():
    return "".join(secrets.choice(ID_ALPHABET) for _ in range(12))


def clean_id(raw):
    """Devolve o ID se o formato for válido; senão None (sem consultar nada)."""
    raw = (raw or "").strip()
    return raw if ID_PATTERN.fullmatch(raw) else None


def _read_sheet(sheet_id):
    """Lê a primeira aba de uma planilha do Google, como lista de dicts.

    Credencial padrão do Google (nenhuma chave no código): a identidade do
    ambiente onde o serviço roda, o login local da CLI do Google, ou um arquivo
    de credencial em GOOGLE_APPLICATION_CREDENTIALS.
    """
    import google.auth
    import gspread

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    gc = gspread.authorize(creds)
    # Tudo como texto: preserva zeros à esquerda de CPF/RG e IDs numéricos.
    return gc.open_by_key(sheet_id).sheet1.get_all_records(numericise_ignore=["all"])


def load_records():
    return _read_sheet(os.environ["SHEET_ID"])


def load_conteudos():
    """Planilha com o conteúdo de cada curso: colunas curso | semestre | item."""
    return _read_sheet(os.environ["CONTEUDOS_SHEET_ID"])


def conteudo_do_curso(rows, curso):
    """[(semestre, item), ...] do curso, na ordem da planilha."""
    key = str(curso).strip().casefold()
    return [
        (str(r.get("semestre", "")).strip(), str(r["item"]).strip())
        for r in rows
        if str(r.get("curso", "")).strip().casefold() == key and str(r.get("item", "")).strip()
    ]


def find(records, doc_id):
    """A linha com esse ID, ou None. ID repetido na planilha é ambíguo: nenhuma
    linha é escolhida, e o documento não valida até a planilha ser corrigida."""
    doc_id = clean_id(doc_id)
    if doc_id is None:
        return None
    matches = [r for r in records if str(r.get("id", "")).strip() == doc_id]
    return matches[0] if len(matches) == 1 else None


def public_view(record):
    """Únicos campos que a validação pública expõe. Nunca CPF, RG ou endereço."""
    template = TEMPLATES.get(str(record.get("tipo_documento", "")).strip())
    try:
        data = format_date_pt(parse_date(record.get("data_emissao", "")))
    except ValueError:
        data = ""
    return {
        "tipo": template.NOME if template else "",
        "nome": str(record.get("nome", "")).strip(),
        "curso": str(record.get("curso", "")).strip(),
        "carga_horaria": str(record.get("carga_horaria", "")).strip(),
        "data_emissao": data,
        "valido": str(record.get("status", "")).strip().lower() == "ativo" and template is not None,
    }
