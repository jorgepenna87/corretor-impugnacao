// ─── PDF.js ───────────────────────────────────────────────────────────────────
import * as pdfjsLib from 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379/pdf.min.mjs';
pdfjsLib.GlobalWorkerOptions.workerSrc =
  'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379/pdf.worker.min.mjs';
window._pdfjsLib = pdfjsLib;

// Corretor é injetado pelo corretor.js como window.Corretor
const { parsePJC, grade, gradeTexto } = window.Corretor;

// ─── Dimensões ────────────────────────────────────────────────────────────────
const DIMENSOES = {
  1:  "Período de cálculo",
  2:  "Verbas deferidas apuradas",
  3:  "Descontos do crédito",
  4:  "Atualização monetária",
  5:  "Divisor e maior remuneração",
  6:  "Frequência nos cartões",
  7:  "Jornada extraordinária",
  8:  "Jornada em feriados",
  9:  "Quantidade mensal",
  10: "Verbas — período",
  11: "Verbas — dedução de pagos",
  12: "Verbas — dias RSR",
  13: "Verbas — incidências",
  14: "Verbas — metodologia",
  15: "Verbas — proporcionalidade férias",
  16: "Juros e correção",
  17: "Base FGTS",
  18: "Base multa 40%",
  19: "Contribuição paga no contrato",
  20: "IRPF",
  21: "INSS — SIMPLES / desoneração / filantropia",
  22: "INSS — SAT/RAT pelo CNAE",
  23: "Custas pagas deduzidas",
  24: "Danos morais — juros sobre indenização",
};

const LABELS_TOTAIS = {
  totalDevidoReclamado: "Total Devido pelo Reclamado",
  liquidoReclamante:    "Líquido Devido ao Reclamante",
  brutoReclamante:      "Bruto Devido ao Reclamante",
  depositoFGTS:         "Depósito FGTS",
  multaFGTS:            "Multa FGTS 40%",
  inssEmpresa:          "INSS Empresa",
  sat:                  "SAT/RAT",
  honorarios:           "Honorários",
  custas:               "Custas",
};

// ─── Estado ──────────────────────────────────────────────────────────────────
let gabarito = null;
let aulasMap  = null;   // { "16": [{titulo, link}, ...], ... }
let ultimoResultado = null;

// ─── Helpers ─────────────────────────────────────────────────────────────────
function fmtBRL(v) {
  if (v == null || v === "" || isNaN(Number(v))) return "—"; // nunca "R$ NaN"
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

// Checkpoints de alíquota (%): não formatar como R$
const CHAVES_ALIQUOTA = new Set(["aliquotaEmpresaFixa", "aliquotaRATFixa"]);
function fmtPct(v) {
  if (v == null || v === "" || isNaN(Number(v))) return "—";
  return Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + "%";
}
// Formata o valor de um item do boletim conforme o tipo/chave
function fmtValorItem(it) {
  if (it.seuValor == null) return "—";
  if (it.tipo === "numero") {
    return CHAVES_ALIQUOTA.has(it.key) ? fmtPct(it.seuValor) : fmtBRL(it.seuValor);
  }
  return String(it.seuValor);
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setStatus(msg) {
  document.getElementById("status-msg").textContent = msg;
}

function notaClass(n) {
  return n >= 8 ? "alto" : n >= 6 ? "medio" : "baixo";
}
function boxClass(n) {
  return n >= 8 ? "destaque-ok" : n >= 6 ? "destaque-med" : "destaque-low";
}

// ─── Carregar gabarito + aulas ────────────────────────────────────────────────
async function carregarGabarito(id) {
  document.getElementById("ex-status").textContent = "Carregando…";
  try {
    const r = await fetch(`../exercicios/${id}/gabarito.json`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    gabarito = await r.json();
    document.getElementById("ex-status").textContent = `(${gabarito.exercicio.titulo})`;
  } catch (e) {
    document.getElementById("ex-status").textContent =
      "Erro ao carregar gabarito (" + e.message + ") — abra pelo start.bat ou por http://localhost:8000/app/, não pelo arquivo direto (file://).";
    gabarito = null;
  }
  // Aulas — opcional; falha silenciosa
  try {
    const r2 = await fetch(`../exercicios/${id}/aulas.json`);
    if (r2.ok) aulasMap = await r2.json();
    else aulasMap = null;
  } catch { aulasMap = null; }
}

const _exSelect = document.getElementById("ex-select");
// Pré-seleção via querystring (?ex=<id>), se for um exercício válido
const _qsEx = new URLSearchParams(location.search).get("ex");
if (_qsEx && [..._exSelect.options].some(o => o.value === _qsEx)) _exSelect.value = _qsEx;
_exSelect.addEventListener("change", function() {
  carregarGabarito(this.value);
});
(async () => { await carregarGabarito(_exSelect.value); })();

// ─── Parse PDF ────────────────────────────────────────────────────────────────
async function extractPdfText(file) {
  // Reconstrói as LINHAS VISUAIS do PDF (o relatório do PJe-Calc é ROTACIONADO 90°:
  // transform=[0,10,-10,0,...] — o texto corre na vertical, então a linha é indexada
  // por X, não por Y). O texto "corrido" antigo misturava colunas/células e fazia o
  // rótulo casar com número de outra célula (bug do "Bruto 681,03"); o cabeçalho
  // "Descrição do Bruto Devido ao Reclamante…" também casava antes da linha real.
  const pdfjsLib = window._pdfjsLib;
  if (!pdfjsLib) return "";
  const ab  = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: new Uint8Array(ab) }).promise;
  let text = "";
  for (let i = 1; i <= pdf.numPages; i++) {
    const page    = await pdf.getPage(i);
    const content = await page.getTextContent();
    let nv = 0, nh = 0, somaC = 0;
    for (const it of content.items) {
      if (!it.str || !it.str.trim()) continue;
      (Math.abs(it.transform[1]) > Math.abs(it.transform[0])) ? nv++ : nh++;
      somaC += it.transform[2];
    }
    const vert   = nv > nh;                              // página rotacionada 90°/270°
    const linhas = new Map();                            // coord da linha -> [{pos, str}]
    for (const it of content.items) {
      if (!it.str || !it.str.trim()) continue;
      const t   = it.transform;
      const lin = Math.round((vert ? t[4] : t[5]) / 2) * 2;   // tolerância ~2pt
      const pos = vert ? t[5] * Math.sign(t[1] || 1) : t[4] * Math.sign(t[0] || 1);
      if (!linhas.has(lin)) linhas.set(lin, []);
      linhas.get(lin).push({ pos, str: it.str });
    }
    const desc = vert ? (somaC < 0) : true;              // direção de leitura topo -> base
    for (const lin of [...linhas.keys()].sort((a, b) => desc ? b - a : a - b)) {
      text += linhas.get(lin).sort((a, b) => a.pos - b.pos).map(p => p.str).join(" ") + "\n";
    }
  }
  return text;
}

async function extractTextFile(file) {
  if (!file) return "";
  const name = file.name.toLowerCase();
  if (name.endsWith(".txt")) return file.text();
  if (name.endsWith(".pdf")) return extractPdfText(file);
  if (name.endsWith(".docx")) return extractDocxText(file);
  if (name.endsWith(".doc")) {
    alert("Arquivos .doc (Word antigo) não são suportados. Salve como .docx (ou .pdf) e reenvie.");
    return "";
  }
  return "";
}

// .docx é um ZIP com word/document.xml. Reusa o JSZip já carregado (sem recalcular nada).
async function extractDocxText(file) {
  const zip = await JSZip.loadAsync(file);
  const docFile = zip.file("word/document.xml");
  if (!docFile) return "";
  const xml = await docFile.async("string");
  const doc = new DOMParser().parseFromString(xml, "application/xml");
  // Cada <w:p> = um parágrafo; o texto fica nos <w:t> (namespace-agnóstico via "*").
  const paras = doc.getElementsByTagNameNS("*", "p");
  if (paras.length) {
    const linhas = [];
    for (const p of paras) {
      const ts = p.getElementsByTagNameNS("*", "t");
      let linha = "";
      for (const t of ts) linha += t.textContent;
      linhas.push(linha);
    }
    return linhas.join("\n");
  }
  // fallback: extrai o conteúdo de todos os <w:t> por regex
  return (xml.match(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g) || [])
    .map(s => s.replace(/<[^>]+>/g, "")).join(" ");
}

// Extrai totais do relatório PDF do aluno (só valor do aluno, não o do gabarito)
// Gap rótulo→número limitado a 40 chars sem dígito/quebra: em PDF multi-coluna o
// número logo após o rótulo pode ser de OUTRA coluna (caso real: bruto 681,03
// com líquido 50.806,17). Se o número estiver longe, melhor "não localizado".
function parseTotaisAluno(text) {
  // cada chave aceita uma LISTA de padrões: o 1º que casar vence (o mais específico
  // primeiro — "HONORÁRIOS LÍQUIDOS…" antes do genérico, que casava "IRRF SOBRE
  // HONORÁRIOS… 0,00"; a seção de totais chama o depósito só de "FGTS <valor>")
  const pats = [
    ["totalDevidoReclamado", [/Total Devido pelo Reclamado[^\d\n]{0,40}([\d.]+,\d{2})/i]],
    ["liquidoReclamante",    [/L[ií]quido Devido ao Reclamante[^\d\n]{0,40}([\d.]+,\d{2})/i]],
    ["brutoReclamante",      [/Bruto Devido ao Reclamante[^\d\n]{0,40}([\d.]+,\d{2})/i]],
    ["depositoFGTS",         [/Dep[oó]sito FGTS[^\d\n]{0,40}([\d.]+,\d{2})/i,
                              /(?:^|\n)FGTS ([\d.]+,\d{2})/]],
    ["multaFGTS",            [/Multa\s*40%[^\d\n]{0,40}([\d.]+,\d{2})/i]],
    ["inssEmpresa",          [/INSS Empresa[^\d\n]{0,40}([\d.]+,\d{2})/i]],
    ["sat",                  [/SAT[^\d\n]{0,40}([\d.]+,\d{2})/i]],
    ["honorarios",           [/Honor[aá]rios L[ií]quidos para Patrono[^\d\n]{0,40}([\d.]+,\d{2})/i,
                              /Honor[aá]rios[^\d\n]{0,40}([\d.]+,\d{2})/i]],
    ["custas",               [/Custas[^\d\n]{0,40}([\d.]+,\d{2})/i]],
  ];
  const out = {};
  for (const [key, lista] of pats) {
    for (const pat of lista) {
      const m = text.match(pat);
      if (m) {
        const v = Math.round(parseFloat(m[1].replace(/\./g, "").replace(",", ".")) * 100) / 100;
        if (v > 0) { out[key] = v; break; }   // 0,00 = casou linha errada; tenta o próximo padrão
      }
    }
  }
  // Sanity check pós-parse: total <= 0 (ou NaN) = captura suspeita → descarta o campo
  for (const key of Object.keys(out)) {
    if (!(out[key] > 0)) { delete out[key]; out._suspeito = true; }
  }
  // Bruto nunca pode ser menor que o líquido — se for, o bruto veio de coluna errada
  if (out.brutoReclamante != null && out.liquidoReclamante != null &&
      out.brutoReclamante < out.liquidoReclamante) {
    delete out.brutoReclamante;
    out._suspeito = true;
  }
  return Object.keys(out).some(k => k !== "_suspeito") ? out : null;
}

// ─── Corrigir ────────────────────────────────────────────────────────────────
window.corrigir = async function() {
  if (!gabarito) { alert("Gabarito não carregado.\n\nO app precisa ser aberto por um servidor (não dá pra abrir o arquivo direto / file://).\nUse o start.bat na pasta do projeto, ou rode 'python -m http.server' na RAIZ do projeto e abra http://localhost:8000/app/?ex=marco16"); return; }
  const filePjc   = document.getElementById("file-pjc").files[0];
  const filePdf   = document.getElementById("file-pdf").files[0];
  const fileTexto = document.getElementById("file-texto").files[0];
  if (!filePjc) { alert("Selecione o arquivo .PJC."); return; }

  setStatus("Analisando o cálculo…");
  document.getElementById("result").style.display = "none";

  try {
    // Parse PJC via corretor.js (window.Corretor)
    const { params, verbas, verbasPrincipais } = await parsePJC(filePjc, JSZip, null);

    // Totais do relatório PDF (opcional)
    let totaisAluno = null;
    if (filePdf) {
      setStatus("Lendo relatório PDF…");
      const pdfText = await extractPdfText(filePdf);
      totaisAluno   = parseTotaisAluno(pdfText);
    }

    // Texto da impugnação (opcional)
    let textoImpug = "";
    if (fileTexto) {
      setStatus("Lendo impugnação…");
      textoImpug = await extractTextFile(fileTexto);
    }

    setStatus("Calculando nota…");
    const resultado     = grade(params, verbas, gabarito, verbasPrincipais, totaisAluno);
    const resultadoText = gradeTexto(textoImpug, gabarito);

    ultimoResultado = { resultado, resultadoText, params, totaisAluno, textoImpug };

    renderResultado(resultado, resultadoText, totaisAluno, !!textoImpug);
        // Análise pedagógica por IA: complementar e assíncrona.
    // Não altera a nota determinística e não bloqueia o resultado se falhar.
    if (textoImpug && window.CorretorAI?.analisar) {
      window.CorretorAI.analisar({
        exercicio: _exSelect.value,
        textoImpug,
        resultado,
        resultadoText,
      }).catch((error) =>
        console.warn("IA pedagógica indisponível:", error)
      );
    } else {
      window.CorretorAI?.resetar?.();
    }
    setStatus("");
    document.getElementById("result").scrollIntoView({ behavior: "smooth" });

    // Diagnóstico detalhado (beta) — Pyodide carrega LAZY, depois da correção.
    // Fire-and-forget: se falhar (offline/CDN/sem canônico), o app segue como hoje.
    rodarDiagnostico(_exSelect.value, filePjc);

  } catch (e) {
    setStatus("Erro: " + e.message);
    console.error(e);
  }
};

// ─── Render principal ─────────────────────────────────────────────────────────
function renderResultado(resultado, resultadoText, totaisAluno, temTexto) {
  document.getElementById("result").style.display = "block";

  const { notaCalculo, pesoOk, pesoTot, boletim } = resultado;

  // ── Nota do cálculo
  const badgeCalc = document.getElementById("badge-calculo");
  badgeCalc.textContent = notaCalculo.toFixed(1);
  badgeCalc.className   = "nota-badge " + notaClass(notaCalculo);
  document.getElementById("box-calculo").className = "nota-box " + boxClass(notaCalculo);
  const divCnt = boletim.filter(b => b.status !== "OK").length;
  document.getElementById("sub-calculo").textContent =
    `${pesoOk.toFixed(0)}/${pesoTot.toFixed(0)} pontos — ${divCnt} item(ns) a corrigir`;

  // ── Nota da impugnação
  const badgeImpug = document.getElementById("badge-impug");
  const subImpug   = document.getElementById("sub-impug");
  const boxImpug   = document.getElementById("box-impug");
  if (temTexto && resultadoText.notaImpugnacao != null) {
    const ni = resultadoText.notaImpugnacao;
    badgeImpug.textContent = ni + "%";
    badgeImpug.className   = "nota-badge " + (ni >= 80 ? "alto" : ni >= 50 ? "medio" : "baixo");
    boxImpug.className     = "nota-box " + (ni >= 80 ? "destaque-ok" : ni >= 50 ? "destaque-med" : "destaque-low");
    const cob  = resultadoText.cobertura || [];
    const falt = cob.filter(c => !c.coberto).length;
    subImpug.textContent = falt === 0
      ? "Todos os temas abordados!"
      : `${falt} tema(s) não encontrado(s) no texto`;
  } else {
    badgeImpug.textContent = "—";
    badgeImpug.className   = "nota-badge medio";
    boxImpug.className     = "nota-box";
    subImpug.textContent   = "Envie o texto da impugnação para avaliar.";
  }

  // ── Totais (só valor do aluno, status bateu/não bateu — sem revelar gabarito)
  renderTotais(totaisAluno);

  // ── Boletim
  renderBoletim(boletim);

  // ── Feedback pedagógico
  renderFeedback(boletim);

  // ── Checklist de texto
  if (temTexto && resultadoText.cobertura?.length) {
    renderChecklist(resultadoText.cobertura);
  } else {
    document.getElementById("card-checklist").style.display = "none";
  }

  // ── CTA de reenvio
  renderCTA(notaCalculo, resultadoText, temTexto);
}

// ─── Totais ────────────────────────────────────────────────────────────────────
// REGRA §10: nunca mostrar o valor do gabarito — só o valor do aluno + status bateu/não bateu
function renderTotais(totaisAluno) {
  const card = document.getElementById("card-totais");
  if (!totaisAluno) {
    // Sem relatório PDF o resultado (total/reflexos) não é conferido — avisar, não esconder.
    card.style.display = "";
    document.getElementById("totais-body").innerHTML =
      '<div class="diff diff-bad" style="display:inline-block">Resultado não conferido</div>' +
      '<p class="hint">Suba o <b>relatório PDF</b> do seu cálculo para conferir o total devido e os reflexos. ' +
      'Sem ele, a nota reflete só os parâmetros do .PJC.</p>';
    return;
  }

  card.style.display = "";
  const gab  = gabarito.totais || {};
  const body = document.getElementById("totais-body");

  let html = '<div class="totais-grid">';
  for (const [key, label] of Object.entries(LABELS_TOTAIS)) {
    const alunoVal = totaisAluno[key];
    const gabVal   = gab[key];
    const ausente  = alunoVal == null || isNaN(Number(alunoVal));
    // Campo que nem existe no exercício e não veio do PDF: não mostrar
    if (ausente && gabVal == null) continue;
    let valHtml, diffHtml = "";
    if (ausente) {
      // Valor descartado/não capturado (PDF multi-coluna etc.) — nunca "R$ NaN"
      valHtml = '<span class="val-ausente">não localizado no PDF</span>';
    } else {
      valHtml = fmtBRL(alunoVal);
      if (gabVal != null) {
        const d = Math.abs(alunoVal - gabVal);
        // Mostrar só bateu/não bateu — não o valor do gabarito
        if (d <= 0.05) {
          diffHtml = `<div class="diff diff-ok">Valor correto</div>`;
        } else {
          diffHtml = `<div class="diff diff-bad">Valor a revisar</div>`;
        }
      }
    }
    html += `<div class="total-item">
      <div class="lbl">${esc(label)}</div>
      <div class="val">${valHtml}</div>
      ${diffHtml}
    </div>`;
  }
  html += "</div>";
  body.innerHTML = html;
}

// ─── Boletim por dimensão ─────────────────────────────────────────────────────
// REGRA §10: sem coluna "esperado", sem revelar o gabarito
function renderBoletim(boletim) {
  const byDim = new Map();
  for (const it of boletim) {
    if (!byDim.has(it.dimensao)) byDim.set(it.dimensao, []);
    byDim.get(it.dimensao).push(it);
  }

  let html = "";
  for (const [dim, items] of [...byDim.entries()].sort((a, b) => a[0] - b[0])) {
    const oks    = items.filter(i => i.status === "OK").length;
    const rever  = items.length - oks;
    const dLabel = DIMENSOES[dim] || `Dimensão ${dim}`;
    const bCls   = rever === 0 ? "badge-ok" : oks === 0 ? "badge-div" : "badge-mixed";
    const bTxt   = rever === 0 ? "OK" : `${rever} a rever`;

    html += `<div class="dim-section">
      <div class="dim-header" onclick="toggleDim(this)">
        <span>D${dim} — ${esc(dLabel)}</span>
        <span class="badge ${bCls}">${bTxt}</span>
      </div>
      <div class="dim-body${rever > 0 ? " open" : ""}">
        <table>
          <thead><tr>
            <th>Item</th>
            <th>Seu valor</th>
            <th>Status</th>
          </tr></thead>
          <tbody>`;

    for (const it of items) {
      const vFmt = fmtValorItem(it);
      const stHtml = it.status === "OK"
        ? `<span class="status-ok">OK</span>`
        : it.status === "DIVERGENTE"
          ? `<span class="status-div">REVER</span>`
          : `<span class="status-aus">AUSENTE</span>`;

      html += `<tr>
        <td>${esc(it.label)}</td>
        <td>${esc(String(vFmt))}</td>
        <td>${stHtml}</td>
      </tr>`;
    }

    html += "</tbody></table></div></div>";
  }
  document.getElementById("boletim-body").innerHTML = html || "<p>Sem itens.</p>";
}

// ─── Feedback pedagógico ──────────────────────────────────────────────────────
// Para cada dimensão com status REVER: seu valor + ponteiro de estudo
function renderFeedback(boletim) {
  const card = document.getElementById("card-feedback");
  const body = document.getElementById("feedback-body");

  // Agrupar itens REVER por dimensão
  const dimsRever = new Map();
  for (const it of boletim) {
    if (it.status === "OK") continue;
    if (!dimsRever.has(it.dimensao)) dimsRever.set(it.dimensao, []);
    dimsRever.get(it.dimensao).push(it);
  }

  if (dimsRever.size === 0) {
    card.style.display = "none";
    return;
  }
  card.style.display = "";

  let html = "";
  for (const [dim, items] of [...dimsRever.entries()].sort((a, b) => a[0] - b[0])) {
    const dLabel = DIMENSOES[dim] || `Dimensão ${dim}`;
    // Aulas cadastradas para esta dimensão
    const aulasDim = aulasMap?.[String(dim)] || [];

    html += `<div class="feedback-dim">
      <div class="fd-titulo">D${dim} — ${esc(dLabel)} <span style="color:var(--bad);font-weight:normal;">— revise e refaça</span></div>`;

    for (const it of items) {
      const vFmt = fmtValorItem(it);
      const statusLabel = it.status === "AUSENTE" ? "não informado" : "valor enviado";
      html += `<div class="fd-valor">
        <strong>${esc(it.label)}:</strong> ${esc(String(vFmt ?? "—"))} <em>(${statusLabel})</em>
      </div>`;
    }

    if (aulasDim.length) {
      html += `<div class="fd-aula">Estude: `;
      html += aulasDim.map(a =>
        a.link
          ? `<a href="${esc(a.link)}" target="_blank">${esc(a.titulo)}</a>`
          : esc(a.titulo || `aulas de ${dLabel}`)
      ).join(" · ");
      html += `</div>`;
    } else {
      html += `<div class="fd-aula">Revise as aulas sobre: <em>${esc(dLabel)}</em></div>`;
    }

    html += `</div>`;
  }
  body.innerHTML = html;
}

// ─── Checklist de temas ───────────────────────────────────────────────────────
function renderChecklist(cobertura) {
  const card = document.getElementById("card-checklist");
  card.style.display = "";
  const body = document.getElementById("checklist-body");
  const faltDiv = document.getElementById("checklist-faltando");

  let html = "";
  const faltando = [];
  for (const item of cobertura) {
    const dim = DIMENSOES[item.dimensao] ? ` (D${item.dimensao} — ${DIMENSOES[item.dimensao]})` : "";
    html += `<div class="checklist-item">
      <div class="chk-icon ${item.coberto ? "chk-ok" : "chk-fail"}">${item.coberto ? "✔" : "✘"}</div>
      <div>
        <div class="chk-label">${esc(item.tema)}</div>
        <div class="chk-nota">${esc(dim)}</div>
        ${!item.coberto && item.explicacao ? `<div style="font-size:13px;color:var(--text-muted);margin-top:4px">${esc(item.explicacao)}</div>` : ""}
      </div>
    </div>`;
    if (!item.coberto) faltando.push(item.tema);
  }
  body.innerHTML = html;

  if (faltando.length) {
    faltDiv.textContent =
      "Temas não abordados: " + faltando.join("; ") +
      ". Inclua esses pontos na impugnação e reenvie.";
  } else {
    faltDiv.textContent = "";
  }
}

// ─── CTA de reenvio ──────────────────────────────────────────────────────────
function renderCTA(notaCalculo, resultadoText, temTexto) {
  const ni = resultadoText?.notaImpugnacao;
  const impugOk = !temTexto || (ni != null && ni >= 80);
  const calcOk  = notaCalculo >= 8;
  const tudo_ok = calcOk && impugOk && temTexto;

  const card    = document.getElementById("card-cta");
  const titulo  = document.getElementById("cta-titulo");
  const texto   = document.getElementById("cta-texto");
  const lista   = document.getElementById("cta-lista");

  if (tudo_ok) {
    card.className = "cta-box cta-parabens";
    titulo.textContent = "Muito bom! Você chegou lá.";
    texto.textContent =
      "Seu cálculo e sua impugnação estão dentro do esperado. " +
      "Agora compare com a correção da aula na mentoria para ver se há nuances que você pode refinar.";
    lista.innerHTML = "";
  } else {
    card.className = "cta-box cta-refaz";
    titulo.textContent = "Ainda não é a versão final — você consegue chegar lá!";
    const pontos = [];
    if (!calcOk) pontos.push("Revise as dimensões marcadas como REVER no boletim e corrija os parâmetros no PJe-Calc.");
    if (temTexto && ni != null && ni < 80) pontos.push("Acrescente os temas que faltaram na impugnação.");
    if (!temTexto) pontos.push("Escreva a impugnação e envie o texto para avaliar a cobertura de temas.");
    pontos.push("Suba o novo .PJC e o texto da impugnação usando o botão abaixo.");

    texto.textContent =
      "Estude as aulas indicadas no feedback acima, refaça o cálculo no PJe-Calc e a impugnação, " +
      "depois suba os arquivos novamente.";
    lista.innerHTML = pontos.map(p => `<li>${esc(p)}</li>`).join("");
  }
}

// ─── Diagnóstico detalhado (beta) — motor Python via Pyodide ─────────────────
// Não mexe na nota: roda o comparar_calculos (diff+raiz) só como diagnóstico extra.
// REGRA §10 vale aqui também: nunca mostrar valor do gabarito (strip no diagnostico.py).
let _pyodidePromise = null; // cache — inicializa uma vez por sessão

function initPyodideDiag() {
  if (_pyodidePromise) return _pyodidePromise;
  _pyodidePromise = (async () => {
    if (typeof loadPyodide === "undefined") throw new Error("Pyodide indisponível (CDN)");
    const py = await loadPyodide();
    const [motor, diag] = await Promise.all([
      fetch("motor/comparar_calculos.py").then(r => { if (!r.ok) throw new Error("motor ausente"); return r.text(); }),
      fetch("motor/diagnostico.py").then(r => { if (!r.ok) throw new Error("diagnostico ausente"); return r.text(); }),
    ]);
    py.FS.writeFile("comparar_calculos.py", motor);
    py.FS.writeFile("diagnostico.py", diag);
    await py.runPythonAsync("import sys; sys.path.insert(0, '.')\nimport json, comparar_calculos, diagnostico");
    return py;
  })();
  // se a inicialização falhar, permite nova tentativa na próxima correção
  _pyodidePromise.catch(() => { _pyodidePromise = null; });
  return _pyodidePromise;
}

async function rodarDiagnostico(exId, filePjc) {
  const card = document.getElementById("card-diagnostico");
  card.style.display = "none";
  try {
    // Sem gabarito canônico (404) → exercício sem card beta, sai calado
    const r = await fetch(`../exercicios/${exId}/gabarito_canonico.json`);
    if (!r.ok) return;
    const gabCanon = await r.text();

    document.getElementById("diag-status").textContent = "carregando o motor detalhado…";
    card.style.display = "";
    const py = await initPyodideDiag();

    const bytes = new Uint8Array(await filePjc.arrayBuffer());
    py.FS.writeFile("aluno.pjc", bytes);
    py.globals.set("GAB_CANON_JSON", gabCanon);
    const out = await py.runPythonAsync(`
import json, comparar_calculos as C, diagnostico
_aluno = C.carregar("aluno.pjc")
_gab = json.loads(GAB_CANON_JSON)
json.dumps(diagnostico.diagnosticar(_aluno, _gab), ensure_ascii=False)
`);
    document.getElementById("diag-status").textContent = "";
    renderDiagnostico(JSON.parse(out));
  } catch (e) {
    // Falha do Pyodide/CDN/parse: esconde o card e segue — a correção já foi exibida
    card.style.display = "none";
    console.warn("Diagnóstico detalhado (beta) indisponível:", e);
  }
}

// Valor do aluno no card do diagnóstico (número → padrão pt-BR; resto → texto cru)
function fmtValorDiag(v) {
  if (v == null || v === "") return null;
  const n = Number(v);
  if (!isNaN(n) && typeof v !== "boolean") {
    return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return String(v);
}

function renderDiagnostico(diag) {
  const card  = document.getElementById("card-diagnostico");
  const body  = document.getElementById("diagnostico-body");
  const itens = diag.itens || [];
  card.style.display = "";

  if (!itens.length) {
    body.innerHTML = '<p class="diag-vazio">Nenhuma divergência de parâmetro encontrada pelo motor detalhado. Muito bom!</p>';
    return;
  }

  let html = "";
  for (const it of [...itens].sort((a, b) => (a.dim || 0) - (b.dim || 0))) {
    const val = fmtValorDiag(it.seu_valor);
    html += `<div class="diag-item">
      <div class="diag-dim">D${esc(it.dim)} · ${esc(it.dim_nome || DIMENSOES[it.dim] || "")}</div>
      <div class="diag-chave">${esc(it.chave || "")}${val != null ? ` — <span class="diag-valor">seu valor: ${esc(val)}</span>` : ""}</div>
      <div class="diag-dica">→ ${esc(it.dica || "")}</div>
    </div>`;
  }
  if (diag.cascata_qtd) {
    html += `<p class="diag-cascata">+ ${esc(diag.cascata_qtd)} diferença(s) em cascata decorrente(s) dos itens acima — corrigindo as raízes, elas somem.</p>`;
  }
  body.innerHTML = html;
}

// ─── Toggle dimensão ──────────────────────────────────────────────────────────
window.toggleDim = function(header) {
  header.nextElementSibling.classList.toggle("open");
};

// ─── Reenvio (rola para o upload) ────────────────────────────────────────────
window.iniciarReenvio = function() {
  document.querySelector(".card").scrollIntoView({ behavior: "smooth" });
};

// ─── Baixar boletim (.txt) ───────────────────────────────────────────────────
// REGRA §10: o boletim baixado também nunca revela o gabarito
window.baixarBoletim = function() {
  if (!ultimoResultado) return;
  const { resultado, resultadoText, totaisAluno, textoImpug } = ultimoResultado;
  const { notaCalculo, pesoOk, pesoTot, boletim } = resultado;
  const gab = gabarito;

  let txt = `BOLETIM DE CORREÇÃO — ${gab.exercicio.titulo}\n`;
  txt += `Exercício: ${gab.exercicio.id} | Processo: ${gab.exercicio.processo}\n`;
  txt += `Data: ${new Date().toLocaleDateString("pt-BR")}\n`;
  txt += "=".repeat(60) + "\n\n";
  txt += `NOTA DO CÁLCULO: ${notaCalculo.toFixed(1)} / 10  (${pesoOk}/${pesoTot} pontos)\n`;

  if (resultadoText?.notaImpugnacao != null) {
    txt += `COBERTURA DA IMPUGNAÇÃO: ${resultadoText.notaImpugnacao}%\n`;
  }
  txt += "\n";

  // Totais (só valor do aluno)
  if (totaisAluno) {
    txt += "SEUS TOTAIS:\n";
    for (const [key, label] of Object.entries(LABELS_TOTAIS)) {
      if (totaisAluno[key] != null) {
        txt += `  ${label}: ${fmtBRL(totaisAluno[key])}\n`;
      }
    }
    txt += "\n";
  }

  // Itens a rever (sem valor esperado)
  const rever = boletim.filter(b => b.status !== "OK");
  if (rever.length) {
    txt += `ITENS A REVER (${rever.length}):\n`;
    for (const it of rever) {
      const dim = `D${it.dimensao} — ${DIMENSOES[it.dimensao] || ""}`;
      txt += `  [${dim}] ${it.label}\n`;
      txt += `    Seu valor: ${it.seuValor ?? "AUSENTE"}\n`;
      const aulasDim = aulasMap?.[String(it.dimensao)] || [];
      if (aulasDim.length) {
        txt += `    Estude: ${aulasDim.map(a => a.titulo).join(", ")}\n`;
      } else {
        txt += `    Revise: aulas sobre ${DIMENSOES[it.dimensao] || `Dimensão ${it.dimensao}`}\n`;
      }
      txt += "\n";
    }
  } else {
    txt += "Nenhum item a rever no cálculo.\n\n";
  }

  // Temas da impugnação faltando
  if (resultadoText?.cobertura?.length) {
    const falt = resultadoText.cobertura.filter(c => !c.coberto);
    if (falt.length) {
      txt += `TEMAS FALTANDO NA IMPUGNAÇÃO (${falt.length}):\n`;
      for (const c of falt) txt += `  - ${c.tema}\n`;
    }
  }

  const blob = new Blob([txt], { type: "text/plain;charset=utf-8" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `boletim_${gab.exercicio.id}_${Date.now()}.txt`;
  a.click();
  URL.revokeObjectURL(url);
};

// ─── Resetar ──────────────────────────────────────────────────────────────────
window.resetar = function() {
  ["file-pjc","file-pdf","file-texto"].forEach(id => {
    document.getElementById(id).value = "";
  });
  document.getElementById("result").style.display = "none";
  setStatus("");
  ultimoResultado = null;
  window.CorretorAI?.resetar?.();
  window.scrollTo({ top: 0, behavior: "smooth" });
};
