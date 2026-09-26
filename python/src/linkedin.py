"""Link "Adicionar ao LinkedIn" para certificados (só certificados, nunca declarações)."""
from urllib.parse import quote, urlencode

from .engine import parse_date
from .templates import TEMPLATES

ADD_URL = "https://www.linkedin.com/profile/add"


def linkedin_url(record, cert_url, organization_name, organization_id=""):
    """URL pré-preenchida, ou None se o registro não for um certificado."""
    tipo = str(record.get("tipo_documento", "")).strip()
    if not tipo.startswith("certificado_") or tipo not in TEMPLATES:
        return None
    emissao = parse_date(record["data_emissao"])
    params = {
        "startTask": "CERTIFICATION_NAME",
        "name": f"{TEMPLATES[tipo].NOME} — {str(record['curso']).strip()}",
        # Com página da empresa no LinkedIn, o ID liga o certificado a ela.
        **({"organizationId": organization_id} if organization_id else {"organizationName": organization_name}),
        "issueYear": emissao.year,
        "issueMonth": emissao.month,
        "certUrl": cert_url,
        "certId": str(record["id"]).strip(),
    }
    return f"{ADD_URL}?{urlencode(params, quote_via=quote)}"
