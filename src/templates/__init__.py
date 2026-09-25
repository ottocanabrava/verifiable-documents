"""Registro de templates: um módulo por tipo de documento.

Cada módulo expõe `NOME` (exibido na validação), `PAGE_SIZE`, `REQUIRED` (colunas obrigatórias além de
`id` e `data_emissao`) e `draw(c, record, issuer)`, que desenha uma página
no canvas do ReportLab. A chave é o valor da coluna `tipo_documento`.
"""
from . import (
    certificado_curso,
    certificado_semestre,
    certificado_trimestre,
    declaracao_matricula,
    declaracao_termino_semestre,
)

TEMPLATES = {
    "certificado_curso": certificado_curso,
    "certificado_trimestre": certificado_trimestre,
    "certificado_semestre": certificado_semestre,
    "declaracao_matricula": declaracao_matricula,
    "declaracao_termino_semestre": declaracao_termino_semestre,
}
