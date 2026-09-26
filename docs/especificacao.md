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
  aleatoriamente (~71 bits): inviável varrer IDs válidos por tentativa.
- Sem `-` ou `_`: em planilhas, um valor começando com `-` vira fórmula.
- Qualquer entrada fora do formato é rejeitada **antes** de consultar a planilha.
- Um ID que aparece em mais de uma linha é ambíguo: nenhuma linha é escolhida,
  a validação responde "Documento não encontrado" e a emissão aponta o problema.

## Validação pública

- O QR code de cada documento aponta para `URL_DE_VALIDACAO?id=<id>`. Essa URL
  vem da configuração, nunca da requisição; sem ela configurada, a emissão falha
  em vez de gerar documento sem QR.
- Resposta para ID válido: **só** tipo, nome, curso, carga horária e data de
  emissão. Nunca CPF, RG, endereço ou qualquer outro dado do aluno.
- ID inexistente ou malformado: "Documento não encontrado", sem erro técnico.
- Limite de consultas por visitante, para dificultar abuso.
- Falha ao ler a planilha: "indisponível" (HTTP 503), sem detalhes técnicos.
- A implementação pode guardar a planilha em cache por até 60 s; uma revogação
  aparece na validação em no máximo esse tempo.
- Todos os tipos são validáveis, inclusive as declarações.

### O que a validação prova

Que, na leitura mais recente do registro (sujeita ao cache acima), o emissor
tem um documento com esse ID, com esses tipo, nome, curso, carga horária e
data, e se ele está ativo ou revogado. **Não** prova que o arquivo PDF em mãos não foi alterado: não há
assinatura digital nem hash do documento, e os campos que a página não mostra
não são conferidos. A comparação entre a página e o documento é de quem confere.

## Adicionar ao LinkedIn

Na validação de um **certificado válido** (nunca declaração, nunca documento
revogado), um botão abre o formulário de certificação do LinkedIn já preenchido:

```
https://www.linkedin.com/profile/add?startTask=CERTIFICATION_NAME
  &name=<Nome do tipo> — <curso>
  &organizationId=<ID da página da instituição>   (ou organizationName=<nome>)
  &issueYear=<ano de emissão>&issueMonth=<mês de emissão>
  &certUrl=<URL de validação do documento>&certId=<id>
```

Todos os valores codificados na URL. Com a página da instituição no LinkedIn,
use `organizationId` (liga o certificado à página); sem ela, `organizationName`.

## Emissão

- Restrita ao emissor (autenticação), com limite de tentativas de senha: ao
  atingir o limite, o cliente fica bloqueado por uma janela curta, inclusive
  para a senha certa. O bloqueio expira sozinho.
- O PDF das declarações contém CPF, RG e endereço: é entregue só ao emissor e
  **nunca** servido pela validação pública.
- Nenhum PDF é armazenado pela validação: o documento é sempre gerado a partir
  da planilha.

## Credenciais

Nenhuma credencial no repositório. O acesso ao Google usa a identidade do
ambiente ou o login da conta do emissor, preferindo sempre o caminho sem chave
de acesso persistente.
