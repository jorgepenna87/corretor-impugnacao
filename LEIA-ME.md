# Corretor de Impugnacao de Calculo — LEIA-ME

App web client-side (zero backend, zero IA) que corrige exercicios de impugnacao
de calculo trabalhista comparando o `.PJC` do aluno contra o gabarito do professor.
Visual no padrao dos apps do `jorgepenna87` (mold "icit / indicadores_trt": Inter +
JetBrains Mono, paleta OKLCH, cards suaves, numeros tabulares).

Arquitetura: **1 motor + 1 `gabarito.json` por exercicio**. Exercicio novo = novo
`gabarito.json`, **zero codigo**. O app carrega `exercicios/<id>/gabarito.json` via
`?ex=<id>` ou pelo seletor.

---

## Exercicios disponiveis (4)

| id           | Caso                                            | Processo                       | Otica     |
|--------------|-------------------------------------------------|--------------------------------|-----------|
| `marco16`    | Sunflow x Alberto Teixeira (diferenca salarial) | 0100912-64.2025.5.01.0005      | Reclamada |
| `abril13`    | Renato x Joalheria Santa Trindade               | 0101079-18.2024.5.01.0005      | Reclamada |
| `junho22`    | Marcio x Comercial Verocity (comissionista/HE)  | 0100333-87.2023.5.01.0005      | Reclamada |
| `setembro15` | Gessi Soares (diarias de viagem / dif. salarial)| 0100681-55.2023.5.01.0248      | Reclamada |

> `marco30` (origem `MARÇO 30 - EXERCÍCIO` no Drive) ainda **nao** e construivel:
> a pasta so tem PDFs de origem, sem `.PJC` gabarito nem submissoes de alunos.

### Resultado das amostras reais (self-check 100% em todos)

| Exercicio    | Self-check     | Amostras (nota)                              |
|--------------|----------------|----------------------------------------------|
| `marco16`    | 21/21 OK       | Andre 7.8 · Bianca 8.9 · Gilmar 7.8 · Sabrina 9.3 |
| `abril13`    | 21/21 OK       | Telma 8.1 · Lisanias 8.1                      |
| `junho22`    | 21/21 OK       | Gilmar 7.0 · Pablo 8.9                        |
| `setembro15` | 19/19 OK       | Miguel 9.2                                    |

Maior diferenciador em todos: **2o indice / data de correcao (ADC 58 / Lei 14.905)**
e SAT-RAT / custas. Motor JS (`corretor.js`) bate **exato** com o `engine.py`
(verificado por `_build/parity.cjs`). Smoke de UI (Playwright) OK nos 4.

---

## Como rodar localmente

O app usa `fetch()` para carregar `gabarito.json`/`aulas.json`, entao **NAO funciona
abrindo o `index.html` direto (file://)**. Sirva a pasta:

```
cd "C:\Users\jorge\Documents\CLAUDE\corretor-impugnacao"
python -m http.server 8000
```
Abra: `http://localhost:8000/app/?ex=marco16` (ou `abril13` / `junho22` / `setembro15`).
Ou use o `start.bat`. No GitHub Pages funciona direto (e servido por HTTP).

---

## Como gerar um gabarito novo (exercicio novo)

A fonte dos exercicios fica em
`G:\Meu Drive\CURSOS EM VIDEO\IMPUGNAÇÃO - EXERCÍCIOS\<DATA> - EXERCÍCIO\`.
Cada pasta tem o `.PJC` gabarito (em `RESULTADO DO EXERCICIO`), o relatorio PDF,
o `CÁLCULOS DO AUTOR.pdf` (calculo a impugnar) e um `PARECER TÉCNICO E IMPUGNAÇÃO.docx`
(a "aula"/correcao escrita do professor — fonte dos temas).

1. **Stage**: copie para `_build/<id>/`:
   `GABARITO.PJC`, `GABARITO_relatorio.pdf`, `ORIGINAL_autor.pdf`, `PARECER.docx`,
   e os `.PJC` dos alunos em `_build/<id>/amostras/`.

2. **Texto da aula -> temas** (analise dos calculos das partes): extraia o texto
   do parecer com `python _build/extract_text.py _build/<id>/PARECER.docx _build/<id>/PARECER.txt`
   e produza `_build/mentoria/<id>_temas.json` (lista de temas com
   `tema, dimensao, dimensao_label, keywords, explicacao_curta` — espelhe
   `_build/mentoria/marco16_temas.json`). E o `textChecklist` da impugnacao.

3. **Config + build**: registre o exercicio em `_build/assemble_configs.py` (metadados,
   `totais_hardcoded` do relatorio, e `drop` de checkpoints que o gabarito nao fixou),
   rode:
   ```
   python _build/assemble_configs.py
   python _build/build_gabarito.py --pjc _build/<id>/GABARITO.PJC \
       --relatorio _build/<id>/GABARITO_relatorio.pdf \
       --config _build/<id>/config.json --out exercicios/<id>/gabarito.json
   cp exercicios/marco16/aulas.json exercicios/<id>/aulas.json
   ```

4. **Valide**:
   ```
   python _build/exrunner.py all <id>     # self-check (deve ser 100%) + nota dos alunos
   node   _build/parity.cjs   <id>        # motor JS == engine.py
   ```
   Se o self-check falhar num checkpoint (gabarito nao fixou aquele parametro -> `esperado` null),
   adicione a `key` ao `drop` do exercicio em `assemble_configs.py` e rebuild.

5. **Registre no app**: adicione um `<option value="<id>">` ao `<select id="ex-select">`
   em `app/index.html`.

---

## Estrutura de arquivos

```
corretor-impugnacao/
  app/
    index.html      # shell (header/seletor/upload/resultado/footer)
    style.css       # design padrao jorgepenna87 (Inter + JetBrains Mono, OKLCH)
    app.js          # UI + render (modulo; espelha a regra no-spoiler)
    corretor.js     # motor parse+grade (browser E node; espelha engine.py)
  exercicios/
    <id>/gabarito.json   # gerado (checkpoints + verbas + totais + textChecklist)
    <id>/aulas.json      # mapa dimensao -> aulas do curso (ponteiro de estudo)
  _build/
    engine.py            # fonte da verdade (parse+grade) — marco16 self-check
    exrunner.py          # runner generico: probe | selfcheck | grade | all <id>
    build_gabarito.py    # .PJC + PDF + config -> gabarito.json
    assemble_configs.py  # metadados + checkpoints padrao + temas -> config.json
    extract_text.py      # .docx/.pdf -> .txt (parecer/relatorio)
    parity.cjs           # confirma motor JS == engine.py
    mentoria/<id>_temas.json   # temas da aula (parecer + analise dos calculos)
    <id>/                # fonte por exercicio (GABARITO.PJC, relatorio, parecer, amostras)
    gabarito/ amostras_alunos/ # fonte do piloto marco16
  start.bat  LEIA-ME.md
```

---

## Regra dura (no-spoiler) — §10 da tarefa

O app **nunca** exibe valor do gabarito: so o valor que O ALUNO enviou + o status
(OK / REVER / AUSENTE) por dimensao + ponteiro de estudo (mapa dimensao->aula) + CTA
para refazer e re-subir. Duas notas separadas: **Cálculo** (% de peso dos checkpoints
corretos) e **Cobertura da Impugnação** (% de temas do `textChecklist` presentes no texto —
so cobertura, nao merito do argumento).

## Formato `.PJC` (resumo tecnico)

- ZIP com um unico XML (ISO-8859-1, entidades HTML numericas).
- Raiz `<Calculo>`; datas em epoch millis; floats em alta precisao.
- JSZip descompacta no browser; DOMParser parseia. **Nunca recalcular valor monetario
  de verba** (o PJe-Calc computa) — graduam-se so parametros single-value exatos; totais
  (manchete) vem do relatorio PDF.

## Como publicar no GitHub Pages

Settings > Pages: branch `main`, pasta `/` (root). Acesse
`https://<usuario>.github.io/<repo>/app/?ex=marco16`.
