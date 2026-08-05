import { readFileSync, existsSync, readdirSync, statSync } from "fs";
import { fileURLToPath } from "url";
import path from "path";
import { createRequire } from "module";
const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const JSZip = require("jszip");
const DOMParser = require("@xmldom/xmldom").DOMParser;
const { parsePJC, grade } = require(path.join(ROOT, "app", "corretor.js"));
const gabarito = JSON.parse(readFileSync(path.join(ROOT, "exercicios", "marco16", "gabarito.json"), "utf-8"));

const DRIVE = "G:\\Meu Drive\\CURSOS EM VIDEO\\IMPUGNAÇÃO - EXERCÍCIOS\\MARÇO 16 - EXERCÍCIO\\EXERCÍCIOS PRONTOS";
function walk(d) {
  let out = [];
  for (const n of readdirSync(d)) {
    const p = path.join(d, n);
    if (statSync(p).isDirectory()) out = out.concat(walk(p));
    else if (n.toUpperCase().endsWith(".PJC")) out.push(p);
  }
  return out;
}
const ENG = { "André":7.8,"Bianca":8.9,"Débora":9.3,"Débora Eug":9.3,"Gilmar":7.8,"NATALIA":8.9,"Natalia":8.9,"Sabrina":9.3,"Vanuza":8.5 };
for (const p of walk(DRIVE)) {
  const who = path.basename(path.dirname(p));
  try {
    const { params, verbas } = await parsePJC(readFileSync(p), JSZip, DOMParser);
    const r = grade(params, verbas, gabarito);
    const key = Object.keys(ENG).find(k => who.toLowerCase().startsWith(k.toLowerCase()));
    const exp = key ? ENG[key] : "?";
    const ok = exp === "?" ? "?" : (r.notaCalculo === exp ? "OK" : "FAIL");
    console.log(`${who.slice(0,32).padEnd(34)} JS=${r.notaCalculo.toFixed(1)}  engine.py=${exp}  ${ok}`);
  } catch (e) {
    console.log(`${who.slice(0,32).padEnd(34)} ERRO: ${e.message}`);
  }
}
