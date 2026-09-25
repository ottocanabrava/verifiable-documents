"""Registro de templates: um módulo por tipo de documento.

Cada módulo expõe `draw(c, record, issuer)`, que desenha uma página no
canvas do ReportLab. A chave é o valor da coluna `tipo_documento`.
"""
from . import certificado_curso

TEMPLATES = {
    "certificado_curso": certificado_curso,
}
