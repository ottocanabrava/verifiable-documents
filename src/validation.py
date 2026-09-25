"""Geração e consulta de IDs de validação."""
import json
import os
import re
import secrets

from .engine import format_date_pt, parse_date
from .templates import TEMPLATES

# 12 caracteres URL-safe = 72 bits aleatórios: impossível varrer por tentativa.
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{12}")


def new_id():
    return secrets.token_urlsafe(9)


def clean_id(raw):
    """Devolve o ID se o formato for válido; senão None (sem consultar nada)."""
    raw = (raw or "").strip()
    return raw if ID_PATTERN.fullmatch(raw) else None


def _read_tab(tab):
    """Lê uma aba da planilha configurada no ambiente, como lista de dicts."""
    import gspread

    if os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        gc = gspread.service_account_from_dict(json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]))
    else:
        gc = gspread.service_account(filename=os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
    # Tudo como texto: preserva zeros à esquerda de CPF/RG e IDs numéricos.
    return gc.open_by_key(os.environ["SHEET_ID"]).worksheet(tab).get_all_records(numericise_ignore=["all"])


def load_records():
    return _read_tab(os.environ.get("SHEET_TAB", "Certificados"))


def load_conteudos():
    """Aba com o conteúdo de cada curso: colunas curso | semestre | item."""
    return _read_tab(os.environ.get("CONTEUDOS_TAB", "Conteudos"))


def conteudo_do_curso(rows, curso):
    """[(semestre, item), ...] do curso, na ordem da planilha."""
    key = str(curso).strip().casefold()
    return [
        (str(r.get("semestre", "")).strip(), str(r["item"]).strip())
        for r in rows
        if str(r.get("curso", "")).strip().casefold() == key and str(r.get("item", "")).strip()
    ]


def find(records, doc_id):
    doc_id = clean_id(doc_id)
    if doc_id is None:
        return None
    return next((r for r in records if str(r.get("id", "")).strip() == doc_id), None)


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
