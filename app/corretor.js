/**
 * corretor.js — motor de parse + grade do corretor de impugnação.
 * Espelha EXATAMENTE engine.py. Funciona no browser E no Node.
 *
 * No browser: carregue JSZip via CDN antes. DOMParser nativo.
 * No Node: instale jszip + @xmldom/xmldom, importe via ESM.
 *
 * API pública:
 *   parsePJC(source)  → { params, verbas }
 *     source = File (browser) | Buffer/Uint8Array (Node)
 *   grade(params, verbas, gabarito) → { notaCalculo, pessoOk, pesoTot, boletim }
 *   gradeTexto(texto, gabarito)     → { notaImpugnacao, cobertura }
 */

// ─── Detecção de ambiente ────────────────────────────────────────────────────
const IS_NODE = typeof process !== "undefined" && process.versions?.node;

// ─── helpers ────────────────────────────────────────────────────────────────

/**
 * Normaliza string: NFKD → ASCII → maiúsculas → colapsa espaços.
 * Espelha engine.py:norm()
 */
function norm(s) {
  if (s == null) return "";
  // NFD para decompor acentos, depois remove combining chars
  let r = String(s).normalize("NFD").replace(/[̀-ͯ]/g, "");
  // Remove não-ASCII residuais
  r = r.replace(/[^\x00-\x7F]/g, "");
  return r.toUpperCase().replace(/\s+/g, " ").trim();
}

/**
 * Converte epoch-ms (string) → "YYYY-MM-DD" em UTC.
 * Espelha engine.py:to_date()
 */
function toDate(ms) {
  if (ms == null || ms === "null" || ms === "") return null;
  const n = parseInt(ms, 10);
  if (isNaN(n)) return null;
  const d = new Date(n);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * Compara valor do aluno x esperado, com tolerância.
 * Espelha engine.py:cmp_val()
 */
function cmpVal(tipo, aluno, esperado, tol) {
  if (aluno == null || aluno === "null" || aluno === "")
    return "AUSENTE";
  if (tipo === "numero") {
    const a = parseFloat(aluno);
    const e = parseFloat(esperado);
    if (isNaN(a) || isNaN(e)) return "DIVERGENTE";
    const t = parseFloat(tol) || 0;
    return Math.abs(Math.round(a * 100) / 100 - Math.round(e * 100) / 100) <= t
      ? "OK"
      : "DIVERGENTE";
  }
  // texto, data, booleano — comparação normalizada
  return norm(String(aluno)) === norm(String(esperado)) ? "OK" : "DIVERGENTE";
}

// ─── Parse XML helpers ───────────────────────────────────────────────────────

/**
 * texto do primeiro filho direto com tag `tag` dentro de `el`.
 */
function txt(el, tag) {
  if (!el) return null;
  const c = el.getElementsByTagName
    ? Array.from(el.childNodes || []).find(n => n.nodeName === tag)
    : null;
  if (!c) return null;
  const t = c.textContent != null ? c.textContent.trim() : null;
  return t || null;
}

/**
 * Busca o primeiro descendente que TEM um filho direto chamado `tag`.
 * Espelha engine.py:parent_with_child()
 * Opera sobre um elemento DOM (browser) ou xmldom element (Node).
 */
function parentWithChild(root, tag) {
  // Iteração em profundidade sobre todos os descendentes
  const stack = [root];
  while (stack.length) {
    const el = stack.pop();
    // Verificar se algum filho direto tem nodeName === tag
    const children = Array.from(el.childNodes || []).filter(n => n.nodeType === 1);
    for (const ch of children) {
      if (ch.nodeName === tag) return el;
    }
    // Empurhar filhos em ordem reversa para preservar ordem de visita
    for (let i = children.length - 1; i >= 0; i--) {
      stack.push(children[i]);
    }
  }
  return null;
}

/**
 * getText de filho direto de `el` pelo nodeName (case-sensitive).
 */
function childText(el, tag) {
  if (!el) return null;
  const children = Array.from(el.childNodes || []).filter(n => n.nodeType === 1);
  const found = children.find(n => n.nodeName === tag);
  if (!found) return null;
  const t = found.textContent != null ? found.textContent.trim() : null;
  return t || null;
}

// ─── extractParams ───────────────────────────────────────────────────────────

/**
 * Extrai todos os parâmetros do documento XML.
 * Espelha engine.py:extract() (sem _verbas — use extractVerbas separado).
 */
function extractParams(doc) {
  const root = doc.documentElement;
  const g = {};

  // Filhos diretos do root por nodeName
  function rootChild(tag) {
    const ch = Array.from(root.childNodes).find(n => n.nodeType === 1 && n.nodeName === tag);
    return ch ? (ch.textContent || "").trim() : null;
  }

  // Período
  for (const k of ["dataAdmissao", "dataDemissao", "dataAjuizamento",
                    "dataInicioCalculo", "dataTerminoCalculo"]) {
    g[k] = toDate(rootChild(k));
  }

  // Remuneração / jornada
  g.valorMaiorRemuneracao   = rootChild("valorMaiorRemuneracao");
  g.valorUltimaRemuneracao  = rootChild("valorUltimaRemuneracao");
  g.valorCargaHorariaPadrao = rootChild("valorCargaHorariaPadrao");
  g.sabadoDiaUtil           = rootChild("sabadoDiaUtil");
  g.diaFechamentoMes        = rootChild("diaFechamentoMes");
  g.regimeDoContrato        = rootChild("regimeDoContrato");
  g.tipoCalculo             = rootChild("tipoCalculo");

  // Prescrição
  g.prescricaoFgts       = rootChild("prescricaoFgts");
  g.prescricaoQuinquenal = rootChild("prescricaoQuinquenal");

  // Parâmetros de atualização — engine usa parent_with_child(root, 'indiceTrabalhista')
  // que encontra ParametrosDeAtualizacao (filho de parametrosDeAtualizacao)
  const corrBlock = parentWithChild(root, "indiceTrabalhista");
  if (corrBlock) {
    for (const k of ["indiceTrabalhista", "combinarOutroIndice",
                     "outroIndiceTrabalhista"]) {
      g[k] = childText(corrBlock, k);
    }
    g.apartirDeOutroIndice = toDate(childText(corrBlock, "apartirDeOutroIndice"));
  }

  // FGTS — engine usa root.find('.//fgts/Fgts')
  const fgtsBlock = findByPath(root, ["fgts", "Fgts"]);
  if (fgtsBlock) {
    g.fgtsAliquota        = childText(fgtsBlock, "aliquota");
    g.incidenciaDoFgts    = childText(fgtsBlock, "incidenciaDoFgts");
    g.multaDoFgts         = childText(fgtsBlock, "multaDoFgts");
    g.excluirAvisoDaMulta = childText(fgtsBlock, "excluirAvisoDaMulta");
  }

  // INSS — engine usa parent_with_child(root, 'aliquotaRATFixa')
  const inssBlock = parentWithChild(root, "aliquotaRATFixa");
  if (inssBlock) {
    g.aliquotaRATFixa       = childText(inssBlock, "aliquotaRATFixa");
    g.aliquotaEmpresaFixa   = childText(inssBlock, "aliquotaEmpresaFixa");
    g.apurarRATPorAtividade = childText(inssBlock, "apurarRATPorAtividade");
  }

  // IRPF — engine usa parent_with_child(root, 'apurarImpostoRenda')
  const irpfBlock = parentWithChild(root, "apurarImpostoRenda");
  if (irpfBlock) {
    g.apurarImpostoRenda = childText(irpfBlock, "apurarImpostoRenda");
  }

  // Custas — engine usa root.find('.//custasJudiciais/CustasJudiciais')
  const custasBlock = findByPath(root, ["custasJudiciais", "CustasJudiciais"]);
  if (custasBlock) {
    g.valorConhecimentoDoReclamado = childText(custasBlock, "valorConhecimentoDoReclamado");
  }

  return g;
}

/**
 * Navega por caminho de tags a partir de um elemento raiz.
 * Cada tag é um filho direto do nível anterior.
 */
function findByPath(root, path) {
  let cur = root;
  for (const tag of path) {
    if (!cur) return null;
    const ch = Array.from(cur.childNodes || [])
      .filter(n => n.nodeType === 1)
      .find(n => n.nodeName === tag);
    if (!ch) return null;
    cur = ch;
  }
  return cur;
}

// ─── extractVerbasPrincipais ─────────────────────────────────────────────────

/**
 * Extrai lista de {descricao, base, devido} das verbas <Calculada> (NAO Reflexo).
 * Soma APENAS ocorrencias diretas (OcorrenciaDeVerba) em verba/ocorrencias/.
 * NAO desce em <calculo><Calculo> aninhado (evita duplicar o valor).
 * Espelha engine.py:extract_verbas_principais() e build_gabarito.py:verbas_principais().
 */
function extractVerbasPrincipais(doc) {
  const root = doc.documentElement;
  const out = [];

  // Localiza o elemento <verbas> como filho direto do root
  const verbasEl = Array.from(root.childNodes || [])
    .filter(n => n.nodeType === 1)
    .find(n => n.nodeName === "verbas");
  if (!verbasEl) return out;

  // Itera todos os descendentes de <verbas> procurando <Calculada>
  function iterAll(el, callback) {
    callback(el);
    for (const ch of Array.from(el.childNodes || []).filter(n => n.nodeType === 1)) {
      iterAll(ch, callback);
    }
  }

  iterAll(verbasEl, el => {
    if (el.nodeName !== "Calculada") return;
    const descEl = Array.from(el.childNodes || []).filter(n => n.nodeType === 1).find(n => n.nodeName === "descricao");
    if (!descEl) return;
    const desc = (descEl.textContent || "").trim();
    if (!desc) return;

    // Localiza <ocorrencias> como filho direto do elemento Calculada
    const occEl = Array.from(el.childNodes || []).filter(n => n.nodeType === 1).find(n => n.nodeName === "ocorrencias");
    let b = 0, dv = 0;
    if (occEl) {
      // Itera todos OcorrenciaDeVerba dentro de <ocorrencias>
      function iterOcc(parent) {
        for (const ch of Array.from(parent.childNodes || []).filter(n => n.nodeType === 1)) {
          if (ch.nodeName === "OcorrenciaDeVerba") {
            const baseEl = Array.from(ch.childNodes || []).filter(n => n.nodeType === 1).find(n => n.nodeName === "base");
            const devidoEl = Array.from(ch.childNodes || []).filter(n => n.nodeType === 1).find(n => n.nodeName === "devido");
            const vb = baseEl ? (baseEl.textContent || "").trim() : null;
            const vd = devidoEl ? (devidoEl.textContent || "").trim() : null;
            if (vb && vb !== "null") b += parseFloat(vb);
            if (vd && vd !== "null") dv += parseFloat(vd);
          } else {
            iterOcc(ch);
          }
        }
      }
      iterOcc(occEl);
    }

    out.push({
      descricao: desc,
      base: Math.round(b * 100) / 100,
      devido: Math.round(dv * 100) / 100,
    });
  });

  return out;
}

// ─── extractVerbas ───────────────────────────────────────────────────────────

/**
 * Extrai config de verbas (descricao normalizada → objeto).
 * Espelha engine.py:extract_verbas().
 * Retorna Map: norm(descricao) → { tipo, descricao, incidenciaINSS, ... }
 */
function extractVerbas(doc) {
  const root = doc.documentElement;
  const out = new Map();

  // verbas > Set > [Calculada|Reflexo]
  const verbasEl = Array.from(root.childNodes || [])
    .filter(n => n.nodeType === 1)
    .find(n => n.nodeName === "verbas");
  if (!verbasEl) return out;

  const setEl = Array.from(verbasEl.childNodes || [])
    .filter(n => n.nodeType === 1)
    .find(n => n.nodeName === "Set");
  if (!setEl) return out;

  const verbas = Array.from(setEl.childNodes || []).filter(n => n.nodeType === 1);
  for (const el of verbas) {
    if (el.nodeName !== "Calculada" && el.nodeName !== "Reflexo") continue;
    const desc = childText(el, "descricao");
    if (!desc) continue;
    const key = norm(desc);
    if (out.has(key)) continue; // primeira ocorrência ganha (igual ao engine.py)
    out.set(key, {
      tipo: el.nodeName,
      descricao: desc,
    });
  }

  return out;
}

// ─── parsePJC ────────────────────────────────────────────────────────────────

/**
 * Parse completo de um .PJC.
 * @param {File|ArrayBuffer|Uint8Array} source
 * @param {object} JSZipLib — instância do JSZip (browser) ou do módulo (Node)
 * @param {object} DOMParserLib — DOMParser class (browser: window.DOMParser; Node: xmldom)
 * @returns {Promise<{ params, verbas }>}
 */
async function parsePJC(source, JSZipLib, DOMParserLib) {
  // Carregar bytes
  let arrayBuf;
  if (source instanceof ArrayBuffer) {
    arrayBuf = source;
  } else if (source instanceof Uint8Array || (typeof Buffer !== "undefined" && Buffer.isBuffer && Buffer.isBuffer(source))) {
    arrayBuf = source.buffer || source;
  } else {
    // File (browser)
    arrayBuf = await source.arrayBuffer();
  }

  const zip = await JSZipLib.loadAsync(arrayBuf);
  const entries = Object.keys(zip.files);
  if (!entries.length) throw new Error("ZIP vazio");

  // Pegar o primeiro arquivo interno (igual ao engine.py)
  const innerName = entries[0];
  const bytes = await zip.files[innerName].async("uint8array");

  // Decodificar ISO-8859-1
  let text;
  if (IS_NODE) {
    // Node: Buffer com encoding
    text = Buffer.from(bytes).toString("latin1");
  } else {
    text = new TextDecoder("iso-8859-1").decode(bytes);
  }

  // Parse XML
  let doc;
  if (DOMParserLib) {
    const parser = new DOMParserLib();
    doc = parser.parseFromString(text, "text/xml");
  } else {
    const parser = new DOMParser();
    doc = parser.parseFromString(text, "text/xml");
    const err = doc.querySelector?.("parsererror");
    if (err) throw new Error("XML inválido: " + err.textContent.slice(0, 80));
  }

  const params = extractParams(doc);
  const verbas = extractVerbas(doc);
  const verbasPrincipais = extractVerbasPrincipais(doc);

  return { params, verbas, verbasPrincipais };
}

// ─── grade ───────────────────────────────────────────────────────────────────

/**
 * Avalia os params/verbas do aluno contra o gabarito.
 * Espelha engine.py:grade().
 * @param {object} params — resultado de extractParams
 * @param {Map} verbas — resultado de extractVerbas (norm(desc) → obj)
 * @param {object} gabarito — objeto gabarito.json
 * @param {Array} [verbasPrincipais] — resultado de extractVerbasPrincipais (opcional)
 * @returns {{ notaCalculo, pesoOk, pesoTot, boletim }}
 */
function grade(params, verbas, gabarito, verbasPrincipais, totaisAluno) {
  const boletim = [];
  let pesoOk = 0, pesoTot = 0;

  for (const ck of gabarito.checkpoints) {
    const alunoVal = params[ck.key] != null ? params[ck.key] : null;
    const status = cmpVal(
      ck.tipo || "texto",
      alunoVal,
      ck.esperado,
      ck.tolerancia || 0
    );
    const peso = ck.peso || 1;
    pesoTot += peso;
    if (status === "OK") pesoOk += peso;

    boletim.push({
      dimensao:  ck.dimensao,
      label:     ck.label,
      key:       ck.key,
      tipo:      ck.tipo || "texto",
      status,
      seuValor:  alunoVal,
      dica:      ck.dica || "",
      peso,
    });
  }

  // verbas_anchor: compara base de cálculo das verbas principais (entra na nota)
  const anchors = gabarito.verbas_anchor || [];
  if (anchors.length > 0 && gabarito.verba_check !== false) {
    const alunoVps = verbasPrincipais || [];
    for (const anchor of anchors) {
      const anchorBase = anchor.base;
      const peso = anchor.peso != null ? anchor.peso : 5;
      pesoTot += peso;

      // procura verba do aluno cuja base casa com a ancora
      let melhor = null;
      let melhorDiff = null;
      for (const vp of alunoVps) {
        const diff = Math.abs(vp.base - anchorBase);
        if (melhorDiff === null || diff < melhorDiff) {
          melhor = vp;
          melhorDiff = diff;
        }
      }

      // verifica tolerancia: abs <= 0.05 OU rel <= 0.5%
      let casa = false;
      if (melhor !== null) {
        const diff = Math.abs(melhor.base - anchorBase);
        const rel = anchorBase !== 0 ? diff / anchorBase : diff;
        casa = (diff <= 0.05) || (rel <= 0.005);
      }

      const status = casa ? "OK" : "DIVERGENTE";
      if (status === "OK") pesoOk += peso;

      boletim.push({
        dimensao: 2,
        label:    "Base de cálculo de verba principal",
        key:      `verba_anchor_${anchor.label.slice(0, 30)}`,
        tipo:     "numero",
        status,
        seuValor: melhor !== null ? melhor.base : null,
        dica:     "D2 — Verbas deferidas apuradas: base de cálculo deve ser a correta",
        peso,
      });
    }
  }

  // totais (RESULTADO) — vindos do relatório PDF; entram na nota. Espelha engine.py.
  // O resultado é a verdade-terra: reflexo a mais / base errada inflam o Total Devido.
  const TOTAIS_GRADE = [
    ["totalDevidoReclamado", "Resultado — Total Devido pelo Reclamado"],
    ["brutoReclamante",      "Resultado — Bruto Devido ao Reclamante"],
    ["liquidoReclamante",    "Resultado — Líquido Devido ao Reclamante"],
  ];
  const gabTotais = gabarito.totais || {};
  const pesoTotal = gabarito.peso_total != null ? gabarito.peso_total : 4;
  if (totaisAluno) {
    for (const [key, label] of TOTAIS_GRADE) {
      const esp = gabTotais[key], al = totaisAluno[key];
      if (esp == null || al == null) continue;
      pesoTot += pesoTotal;
      const diff = Math.abs(Number(al) - Number(esp));
      const rel = esp ? diff / Math.abs(esp) : diff;
      const casa = (diff <= 0.05) || (rel <= 0.005);
      if (casa) pesoOk += pesoTotal;
      boletim.push({
        dimensao: 2, label, key: `total_${key}`, tipo: "numero",
        status: casa ? "OK" : "DIVERGENTE", seuValor: al,
        dica: "Resultado final: o total não confere. Reveja reflexos, base de cálculo e índice no PJe-Calc.",
        peso: pesoTotal,
      });
    }
  }

  const notaCalculo = pesoTot > 0
    ? Math.round((pesoOk / pesoTot) * 10 * 10) / 10
    : 0;

  return { notaCalculo, pesoOk, pesoTot, boletim };
}

// ─── gradeTexto ──────────────────────────────────────────────────────────────

/**
 * Verifica cobertura de temas no texto da impugnação.
 * @param {string} texto
 * @param {object} gabarito
 * @returns {{ notaImpugnacao, cobertura: [{tema, dimensao, coberto}] }}
 */
function gradeTexto(texto, gabarito) {
  if (!gabarito.textChecklist?.length || !texto) {
    return { notaImpugnacao: null, cobertura: [] };
  }
  const textoNorm = norm(texto);
  const cobertura = [];
  let cobertos = 0;

  for (const item of gabarito.textChecklist) {
    const coberto = item.keywords.some(kw => textoNorm.includes(norm(kw)));
    cobertura.push({ tema: item.tema, dimensao: item.dimensao, coberto,
      explicacao: item.explicacao_curta || item.explicacao || "" });
    if (coberto) cobertos++;
  }

  const notaImpugnacao = Math.round((cobertos / gabarito.textChecklist.length) * 100);
  return { notaImpugnacao, cobertura };
}

// ─── Exportação ──────────────────────────────────────────────────────────────

// Node ESM
if (IS_NODE) {
  // export via module.exports para compatibilidade CJS e ESM
  const exports_ = { parsePJC, grade, gradeTexto, norm, cmpVal, toDate,
                     extractParams, extractVerbas };
  if (typeof module !== "undefined") module.exports = exports_;
  // Para ESM: o caller importa como default ou named
  // Exposto em global para o teste
  if (typeof globalThis !== "undefined") Object.assign(globalThis, exports_);
}

// Browser: expõe em window
if (!IS_NODE && typeof window !== "undefined") {
  window.Corretor = { parsePJC, grade, gradeTexto, norm, cmpVal, toDate };
}
