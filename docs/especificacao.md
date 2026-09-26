# Especificação

O contrato que as duas implementações seguem (`python/` e `n8n/`). Mudou uma
regra aqui, as duas mudam juntas.

## Fonte dos dados

Uma planilha do Google, uma linha por documento emitido:

```
id | tipo_documento | nome | curso | carga_horaria | data_emissao | status | cpf | rg | endereco | dia_aula
```

- Colunas em **texto simples**, para a planilha não converter datas nem cortar
  zeros à esquerda de CPF/RG.
- `data_emissao`: `DD/MM/AAAA` ou `AAAA-MM-DD`.
- `status`: só `ativo` é válido. Qualquer outro valor (ex.: `revogado`) faz o
  documento aparecer como "não é mais válido".

Uma segunda planilha guarda o conteúdo programático, uma linha por item:

```
curso | semestre | item
```

O `curso` é comparado sem diferenciar maiúsculas; os itens saem na ordem da
planilha, agrupados por `semestre`.

## Tipos de documento

| `tipo_documento` | Nome exibido | Obrigatórias | Opcionais |
|---|---|---|---|
| `certificado_curso` | Certificado de conclusão de curso | `nome`, `curso`, `carga_horaria` + conteúdo do curso | |
| `certificado_semestre` | Certificado de conclusão de semestre | `nome`, `curso`, `carga_horaria` | |
| `certificado_trimestre` | Certificado de conclusão de trimestre | `nome`, `curso`, `carga_horaria` | |
| `declaracao_matricula` | Declaração de matrícula | `nome`, `curso`, `cpf`, `rg`, `endereco` | `dia_aula`, `carga_horaria` |
| `declaracao_termino_semestre` | Declaração de término de semestre | `nome`, `curso`, `cpf`, `rg`, `endereco` | `dia_aula`, `carga_horaria` |

`id` e `data_emissao` são obrigatórios em todos. O certificado de curso
completo tem uma segunda página com o conteúdo do curso; sem conteúdo
cadastrado, ele não é gerado.

## ID de validação

- 12 caracteres, só letras e dígitos (`[A-Za-z0-9]{12}`), gerados
  aleatoriamente (~71 bits): impossível varrer IDs válidos por tentativa.
- Sem `-` ou `_`: em planilhas, um valor começando com `-` vira fórmula.
- Qualquer entrada fora do formato é rejeitada **antes** de consultar a planilha.

## Validação pública

- O QR code de cada documento aponta para `URL_DE_VALIDACAO?id=<id>`.
- Resposta para ID válido: **só** tipo, nome, curso, carga horária e data de
  emissão. Nunca CPF, RG, endereço ou qualquer outro dado do aluno.
- ID inexistente ou malformado: "Documento não encontrado", sem erro técnico.
- Limite de consultas por visitante, para dificultar abuso.
- Todos os tipos são validáveis, inclusive as declarações.

## Emissão

- Restrita ao emissor (autenticação).
- O PDF das declarações contém CPF, RG e endereço: é entregue só ao emissor e
  **nunca** servido pela validação pública.
- Nenhum PDF é armazenado pela validação: o documento é sempre gerado a partir
  da planilha.

## Credenciais

Nenhuma credencial no repositório. O acesso ao Google usa a identidade do
ambiente ou o login da conta do emissor, preferindo sempre o caminho sem chave
de acesso persistente.
