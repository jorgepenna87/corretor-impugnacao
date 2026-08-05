# TAREFA — App corretor de exercício de impugnação (cálculo trabalhista), SEM IA

## Meta
App web **client-side** (GitHub Pages, igual aos apps do `jorgepenna87`) onde o aluno
sobe o arquivo `.PJC` que exportou do PJe-Calc e recebe uma **correção automática,
determinística, sem nenhuma IA**: nota + boletim de divergências verba a verba e
parâmetro a parâmetro contra o GABARITO do professor, mais um checklist de cobertura
do texto da impugnação.

**Por quê:** Jorge dá exercícios de impugnação na mentoria. Hoje a correção é manual
(no vídeo). O gabarito de cada exercício já existe como um `.PJC`. Queremos escalar a
correção sem IA.

**Critério de sucesso:** rodar o app com as 4 amostras reais em
`_build/amostras_alunos/*.PJC` e produzir, para cada uma, um boletim coerente de
divergências contra o gabarito (`_build/gabarito/GABARITO.PJC`). A engine de diff é
exata (XML), não estatística.

## Restrição dura
- **Zero IA em runtime.** Nada de API, nada de LLM. Só parsing + comparação numérica.
- **Zero OCR.** O `.PJC` é estruturado (ver abaixo). O relatório PDF é digital (tem
  camada de texto) — extrai com pdf.js, não com OCR.
- Client-side puro (roda abrindo o `index.html`, sem build, sem servidor). Vanilla JS.
  Libs por CDN: `JSZip` (descompactar o .PJC) e `pdf.js` (ler total do relatório).
- **Scope guard:** a solução mais simples que funciona. Sem framework, sem features
  não pedidas, sem refactor. Não inventar dimensões além das listadas.

---

## 1. O formato `.PJC` (a descoberta que dispensa OCR)
`.PJC` é um **ZIP** contendo **um único arquivo XML** (extensão interna `.PJC`/`.XML`,
encoding **ISO-8859-1**, uma linha só, muito longa). Raiz `<Calculo>`. Tem TODOS os
parâmetros e verbas do cálculo em tags. Fluxo: `JSZip.loadAsync(file)` → pegar o
arquivo interno → `decode ISO-8859-1` → `DOMParser` → navegar.

### Keypaths já mapeados (use estes, não redescubra do zero)
Tudo abaixo do root `<Calculo>`. Datas vêm em **epoch millis** (string) → converter.

**Período (Dimensão 1):**
- `dataAdmissao`, `dataDemissao`, `dataAjuizamento`, `dataInicioCalculo`, `dataTerminoCalculo`

**Remuneração / jornada (D5, D6):**
- `valorMaiorRemuneracao`, `valorUltimaRemuneracao`, `valorCargaHorariaPadrao`,
  `sabadoDiaUtil`, `diaFechamentoMes`, `regimeDoContrato`, `tipoCalculo`

**Prescrição:**
- `prescricaoFgts`, `prescricaoQuinquenal`

**Correção monetária / índices (D4, D16):** dentro do bloco de parâmetros de atualização
- `indiceTrabalhista` (ex.: `IPCAE`), `tipoDeIndiceDeCorrecao`, `combinarOutroIndice`,
  `outroIndiceTrabalhista` (ex.: `IPCA`), `apartirDeOutroIndice` (data — divisor ADC 58),
  `indicesAcumulados`, `indiceDeCorrecaoDoFGTS`, `indiceDeCorrecaoDasCustas`

**Juros (D16):** `apuracoesDeJuros/Set/ApuracaoDeJuros/taxaDeJuros` (série mensal —
para v1 basta detectar se há juros e a taxa final; não precisa replicar a série)

**FGTS (D17, D18):** bloco `fgts/Fgts`
- `aliquota` (ex.: `OITO_POR_CENTO`), `incidenciaDoFgts` (ex.: `SOBRE_O_TOTAL_DEVIDO`),
  `multaDoFgts` (ex.: `QUARENTA_POR_CENTO`), `indiceMulta`, `excluirAvisoDaMulta`,
  `comporPrincipal`

**INSS / SAT-RAT / terceiros (D21, D22):** no bloco de previdência/atualização
- `aliquotaEmpresa` (ex.: 20.0), `aliquotaSAT` (ex.: 3.0), `aliquotaRATFixa`,
  `apurarRATPorAtividade`, `aliquotaSegurado`, `aliquotaTerceiros`,
  `tipoAliquotaEmpregador`, `periodosComOpcaoSimples` (SIMPLES),
  `valorDevidoSAT`, `valorTotalInssEmpresa`, `valorTotalInssSegurado`

**IRPF (D20):** `apurarImpostoRenda`, `incidenciaIRPF`, `apurarIRPFSobreJuros`, `valorImpostoRenda`

**Custas (D23):** bloco `custasJudiciais/CustasJudiciais`
- `valorConhecimentoDoReclamado`, `tipoDeCustasDeConhecimentoDoReclamado`,
  `pisoCustasConhecimentoReclamado`, `tetoCustasConhecimentoReclamante`

**Verbas (D2, D10, D11, D13, D14):** há um nó `<verbas>` com várias verbas; cada verba
tem `<descricao>` (ex.: `"1. DIFERENÇA SALARIAL"`) e ocorrências mensais
(`OcorrenciaDeVerba`) com `base`, `devido`, `pago`. **Por verba**: somar `devido` das
ocorrências → total devido da verba. A nesting exata você confirma inspecionando o
arquivo (script abaixo). Chave de comparação entre aluno e gabarito = `descricao`
normalizada (uppercase, trim, sem acento).

### Valores
Decimais em alta precisão (ex.: `500.8300000000000000000000000`). Arredondar para 2
casas (centavos) na comparação. Tolerância: `abs(diff) <= 0.05` OU `relativo <= 0.5%`.

---

## 2. `build_gabarito.py` (gerador do gabarito — VOCÊ ESCREVE)
Python (o ambiente tem `pdfplumber`). Uso:
```
python build_gabarito.py --pjc _build/gabarito/GABARITO.PJC \
    --relatorio _build/gabarito/GABARITO_relatorio.pdf \
    --config _build/gabarito/config_marco16.json \
    --out exercicios/marco16/gabarito.json
```
Faz: descompacta o `.PJC`, parseia o XML, extrai os keypaths acima + verbas, lê o
**total geral** do relatório PDF (não está no XML — ver §3), funde com o `config`
(metadados do exercício + checklist de texto curado) e grava `gabarito.json`.

Esse script é também a **referência da lógica de parsing** que o app porta para JS.
Mantenha a extração de keypaths numa função clara, fácil de espelhar em JS.

## 3. Totais (do relatório, não do XML)
O grande total NÃO é armazenado no `.PJC`. Pegar do relatório PDF do gabarito (já
extraídos, gravar no gabarito.json como constantes):
- Total Devido pelo Reclamado: **115.633,43**
- Líquido Devido ao Reclamante: **83.184,53**
- Bruto Devido ao Reclamante: **95.503,45** (verbas 88.395,78 + juros 7.107,67)
- Depósito FGTS: **6.269,24** · Multa 40%: **4.492,79** · INSS empresa: **11.944,10**
- SAT: **1.791,61** · Honorários: **4.472,69** · Custas: **1.507,78**

No lado do aluno: se ele também subir o relatório PDF, extrair o total dele com pdf.js
(regex em "Total Devido pelo Reclamado"/"Líquido Devido ao Reclamante"). Se subir só o
`.PJC`, mostrar o total como "estimado pela soma das verbas" e deixar claro que é
estimativa. O diff por dimensão (do XML) é o núcleo; o total é só manchete.

---

## 4. Schema `gabarito.json`
```json
{
  "exercicio": { "id": "marco16", "titulo": "...", "processo": "0100912-64.2025.5.01.0005",
                 "otica": "RECLAMADA" },
  "checkpoints": [
    { "key": "dataAjuizamento", "dimensao": 1, "label": "Data de ajuizamento",
      "tipo": "data", "esperado": "2025-07-22", "tolerancia": 0, "peso": 1 },
    { "key": "aliquotaSAT", "dimensao": 22, "label": "Alíquota SAT/RAT",
      "tipo": "numero", "esperado": 3.0, "tolerancia": 0, "peso": 1 },
    { "key": "indiceTrabalhista", "dimensao": 16, "label": "Índice de correção",
      "tipo": "texto", "esperado": "IPCAE", "peso": 1 }
  ],
  "verbas": [
    { "descricao": "1. DIFERENÇA SALARIAL", "devido": 51607.45, "tolerancia": 0.5 }
  ],
  "totais": { "totalDevidoReclamado": 115633.43, "liquidoReclamante": 83184.53, "...": 0 },
  "textChecklist": [
    { "tema": "Correção/juros (ADC 58)", "dimensao": 16,
      "keywords": ["ADC 58", "IPCA", "SELIC", "Súmula 439"] },
    { "tema": "SAT/RAT pelo CNAE", "dimensao": 22, "keywords": ["SAT", "RAT", "CNAE"] }
  ]
}
```
- `checkpoints`: parâmetros a comparar (do XML). `build_gabarito.py` preenche `esperado`
  lendo o gabarito; os campos `dimensao/label/peso/tolerancia` vêm do `config`.
- `verbas`: total devido esperado por verba (do XML).
- `textChecklist`: temas que o aluno DEVIA ter levantado na impugnação. **Para v1, semeie
  com os temas das dimensões divergentes deste exercício** (o Jorge vai refinar depois
  com a transcrição da aula). Deixe os keywords editáveis no `config`.

## 5. Engine de diff/nota (JS, no app)
Para cada `checkpoint`: ler o valor do aluno no mesmo keypath → comparar com `esperado`
(por tipo, com tolerância) → status `OK` / `DIVERGENTE` / `AUSENTE`. Idem para `verbas`
(match por `descricao` normalizada). 
- **Nota do cálculo** = % de peso de checkpoints+verbas com status OK.
- **Nota da impugnação** (separada) = % de temas do `textChecklist` cobertos no texto.
- **Boletim** agrupado por **dimensão** (use a lista das 24 no §7). REGRA DURA: ver §10
  — o boletim **nunca** revela o valor esperado/gabarito; mostra só o valor do aluno,
  o status e pra onde estudar.
- **Checklist de texto** (se o aluno subir a impugnação em .txt/.pdf/.docx): extrair o
  texto (pdf.js p/ pdf; para .docx, unzip + `word/document.xml`; .txt direto) e marcar
  cada `tema` como ✔ (algum keyword presente, case/acento-insensitive) ou ✘. Deixar
  CLARO na UI que isto é só **cobertura de temas**, não avaliação do argumento.

## 6. UI (estilo dos apps do Jorge: limpo, PT-BR, uma página)
- Cabeçalho com o título do exercício.
- Área de upload (drag&drop): `.PJC` obrigatório; relatório PDF e impugnação opcionais.
- Resultado: card das **duas notas** (Cálculo / Impugnação), **boletim por dimensão**
  (tabela: dimensão | item | **seu valor** | status), e **checklist do texto**.
  NÃO há coluna "esperado", NÃO há "gabarito", NÃO há "diferença" — ver §10.
- Bloco final de **feedback pedagógico + reenvio** (ver §10).
- Botão "baixar boletim" (gera um .txt/.html simples). Sem login, sem backend.
- Genérico por exercício: o app carrega `exercicios/<id>/gabarito.json` (id via query
  string `?ex=marco16` ou seletor). Exercício novo = novo gabarito.json, zero código.

## 7. As 24 dimensões (rótulos do boletim)
1 Período de cálculo · 2 Verbas deferidas apuradas · 3 Descontos do crédito ·
4 Atualização monetária (índices+datas) · 5 Divisor e maior remuneração ·
6 Frequência nos cartões · 7 Jornada extraordinária · 8 Jornada em feriados ·
9 Quantidade mensal · 10 Verbas-período · 11 Verbas-dedução de pagos ·
12 Verbas-dias RSR · 13 Verbas-incidências · 14 Verbas-metodologia ·
15 Verbas-proporcionalidade férias · 16 Juros e correção · 17 Base FGTS ·
18 Base multa 40% · 19 Contribuição paga no contrato · 20 IRPF-base ·
21 INSS-SIMPLES/desoneração/filantropia · 22 INSS-SAT/RAT pelo CNAE ·
23 Custas pagas deduzidas · 24 Danos morais-S.439 (juros sobre indenização)

## 8. Entregáveis
- `_build/build_gabarito.py`
- `_build/gabarito/config_marco16.json` (você cria com label/dimensão/keywords)
- `exercicios/marco16/gabarito.json` (gerado)
- `app/index.html` (+ js/css inline ou em arquivos; CDN p/ JSZip e pdf.js)
- `LEIA-ME.md` curto: como gerar um gabarito novo e como publicar no GitHub Pages.

## 9. Teste obrigatório antes de entregar
Rode mentalmente/efetivamente as 4 amostras (`_build/amostras_alunos/*.PJC`) contra o
gabarito e confirme no `LEIA-ME` o resultado de cada uma (nota + nº de divergências).
Se alguma amostra não parsear, conserte o parser. Reporte a estrutura de verbas que
você encontrou (descricao + total devido de cada verba do gabarito).

---

## 10. FEEDBACK PEDAGÓGICO — sem spoiler + loop de reenvio  (camada final)
A nota NÃO entrega o gabarito. Ela diagnostica onde o aluno falhou e o manda
estudar/refazer. Objetivo = aprendizado por maestria, não "ver a resposta".

**REGRA DURA (no-spoiler):** o app **nunca** exibe nenhum valor do gabarito —
nem total, nem valor esperado de parâmetro/verba, nem "diferença para o correto".
Só mostra: o valor que O ALUNO enviou, o status (OK / REVER) por dimensão, e a
orientação de estudo. (Os valores do gabarito existem só internamente, no
`gabarito.json`, para o motor comparar — nunca renderizados.)

**Boletim do cálculo:** para cada dimensão com status REVER, mostrar:
`Dimensão N — <nome> · seu valor: <valor do aluno> · ⚠️ revise e refaça` +
ponteiro de estudo (ver aulas abaixo). Dimensões OK: só um ✓ verde, sem detalhe.

**Ponteiro de estudo (aulas):** ler de um mapa `aulas` (campo no `gabarito.json` ou
arquivo `exercicios/<id>/aulas.json`), formato:
`{ "16": [{ "titulo": "Juros e correção — ADC 58", "link": "https://..." }], ... }`
(chave = número da dimensão). Para cada dimensão REVER, listar as aulas daquela
dimensão. Se ainda não houver link cadastrado, mostrar só o nome da dimensão
("revise as aulas sobre <nome da dimensão>"). O mapa é editável pelo Jorge; pode
vir vazio na v1 sem quebrar o app.

**Impugnação:** listar os temas do `textChecklist` que ficaram ✘ →
"Você não abordou: <temas>. Refaça estes itens do checklist e reenvie." (Sem revelar
o argumento — só o tema que faltou.)

**Loop de reenvio (CTA final):** bloco de encerramento com tom de incentivo, ex.:
"Ainda não é a versão final. Reveja as aulas marcadas, refaça o cálculo no PJe-Calc e
a impugnação, e **suba o `.PJC` e a impugnação de novo**." Botão/área de upload
continua disponível para reenviar na hora (o app é stateless; reenviar = re-subir).
Se as duas notas forem altas (ex.: cálculo ≥ limiar configurável e impugnação 100%
de cobertura), trocar o tom para parabéns + "agora compare com a aula da mentoria",
ainda **sem** despejar os números do gabarito.
