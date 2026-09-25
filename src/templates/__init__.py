"""Registro de templates: um módulo por tipo de documento.

Cada módulo expõe `PAGE_SIZE`, `REQUIRED` (colunas obrigatórias além de
`id` e `data_emissao`) e `draw(c, record, issuer)`, que desenha uma página
no canvas do ReportLab. A chave é o valor da coluna `tipo_documento`.
"""
from . import certificado_curso, declaracao_matricula, declaracao_termino_semestre

TEMPLATES = {
    "certificado_curso": certificado_curso,
    "declaracao_matricula": declaracao_matricula,
    "declaracao_termino_semestre": declaracao_termino_semestre,
}
