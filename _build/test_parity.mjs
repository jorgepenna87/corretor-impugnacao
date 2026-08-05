/**
 * test_parity.mjs — Teste de paridade JS vs engine.py
 *
 * Uso: node _build/test_parity.mjs
 *
 * Requer: npm install jszip @xmldom/xmldom  (na pasta _build ou na raiz)
 *
 * Gabarito de paridade (notas do engine.py com os 4 PJCs locais):
 *   aluno_Andre.PJC  → 7.8
 *   aluno_Bianca.PJC → 8.9
 *   aluno_Gilmar.PJC → 7.8
 *   aluno_Sabrina.PJC → 9.3
 */

import { readFileSync, existsSync } from "fs";
import { fileURLToPath } from "url";
import path from "path";
import { createRequire } from "module";

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");

// ─── Dependências ────────────────────────────────────────────────────────────
let JSZip, DOMParser;
try {
  JSZip = require("jszip");
} catch {
  try {
    JSZip = (await import("jszip")).default;
  } catch {
    console.error("ERRO: instale jszip:  npm install jszip");
    process.exit(1);
  }
}
try {
  const xmldom = require("@xmldom/xmldom");
  DOMParser = xmldom.DOMParser;
} catch {
  try {
    const xmldom = await import("@xmldom/xmldom");
    DOMParser = xmldom.DOMParser;
  } catch {
    console.error("ERRO: instale @xmldom/xmldom:  npm install @xmldom/xmldom");
    process.exit(1);
  }
}

// ─── Carregar corretor.js ────────────────────────────────────────────────────
const corretorPath = path.join(ROOT, "app", "corretor.js");
if (!existsSync(corretorPath)) {
  console.error("ERRO: app/corretor.js não encontrado");
  process.exit(1);
}
// Carregar como CJS via require (corretor.js exporta module.exports)
const { parsePJC, grade } = require(corretorPath);

// ─── Carregar gabarito ───────────────────────────────────────────────────────
const gabPath = path.join(ROOT, "exercicios", "marco16", "gabarito.json");
if (!existsSync(gabPath)) {
  console.error("ERRO: exercicios/marco16/gabarito.json não encontrado");
  process.exit(1);
}
const gabarito = JSON.parse(readFileSync(gabPath, "utf-8"));

// ─── Gabarito de paridade (notas esperadas pelo engine.py) ──────────────────
// Estes são os 4 alunos disponíveis localmente.
// Os outros 3 (Débora, Natalia, Vanuza) estão só no Google Drive.
const ESPERADO = {
  "aluno_Andre.PJC":   7.8,
  "aluno_Bianca.PJC":  8.9,
  "aluno_Gilmar.PJC":  7.8,
  "aluno_Sabrina.PJC": 9.3,
};

// ─── Rodar testes ────────────────────────────────────────────────────────────
const amostrasDir = path.join(__dirname, "amostras_alunos");

console.log("=".repeat(65));
console.log("TESTE DE PARIDADE JS vs engine.py");
console.log("=".repeat(65));
console.log();

const rows = [];
let allOk = true;

for (const [fname, esperadaNota] of Object.entries(ESPERADO)) {
  const pjcPath = path.join(amostrasDir, fname);
  if (!existsSync(pjcPath)) {
    rows.push({ fname, nota: "ARQUIVO_AUSENTE", esperado: esperadaNota, ok: false });
    allOk = false;
    continue;
  }

  try {
    const bytes = readFileSync(pjcPath);
    const { params, verbas } = await parsePJC(bytes, JSZip, DOMParser);
    const resultado = grade(params, verbas, gabarito);
    const nota = resultado.notaCalculo;
    const ok = nota === esperadaNota;
    if (!ok) allOk = false;

    // Divergências detalhadas
    const divs = resultado.boletim
      .filter(b => b.status !== "OK")
      .map(b => `${b.key}=${b.seuValor}`);

    rows.push({ fname, nota, esperado: esperadaNota, ok, divs });
  } catch (e) {
    rows.push({ fname, nota: `ERRO: ${e.message}`, esperado: esperadaNota, ok: false });
    allOk = false;
  }
}

// ─── Imprimir resultado ───────────────────────────────────────────────────────
const W = 28;
console.log(`${"ALUNO".padEnd(W)} ${"NOTA_JS".padStart(7)} ${"ESPERADO".padStart(8)} ${"PAR?".padStart(5)}`);
console.log("-".repeat(W + 25));
for (const r of rows) {
  const notaStr = typeof r.nota === "number" ? r.nota.toFixed(1) : String(r.nota);
  const espStr  = typeof r.esperado === "number" ? r.esperado.toFixed(1) : String(r.esperado);
  const par     = r.ok ? "  OK" : " FAIL";
  console.log(`${r.fname.padEnd(W)} ${notaStr.padStart(7)} ${espStr.padStart(8)} ${par}`);
  if (!r.ok && r.divs?.length) {
    console.log(`  divs: ${r.divs.join(", ")}`);
  }
}

console.log();
if (allOk) {
  console.log("RESULTADO: PARIDADE PERFEITA — todos os 4 alunos locais batem com engine.py");
} else {
  console.log("RESULTADO: DIVERGENCIA DETECTADA — verifique os itens acima");
  process.exit(1);
}

console.log();
console.log("Nota: Débora Eugênio (9.3), Natalia Nascimento (8.9), Vanuza Moreira (8.5)");
console.log("      estão no Google Drive e não puderam ser testados localmente.");
