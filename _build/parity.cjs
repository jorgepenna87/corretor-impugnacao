// parity.cjs — confirma que o motor JS (corretor.js) bate com o engine.py.
// Uso: node _build/parity.cjs <id>
const fs = require('fs'), path = require('path');
const JSZip = require('jszip');
const { DOMParser } = require('@xmldom/xmldom');
const C = require(path.join(__dirname, '..', 'app', 'corretor.js'));

const PROJ = path.join(__dirname, '..');
const exid = process.argv[2];

(async () => {
  const gab = JSON.parse(fs.readFileSync(path.join(PROJ, 'exercicios', exid, 'gabarito.json'), 'utf8'));
  const dir = path.join(__dirname, exid, 'amostras');
  const files = fs.readdirSync(dir).filter(f => f.toUpperCase().endsWith('.PJC')).sort();
  console.log(`=== PARITY JS ${exid}: ${files.length} alunos ===`);
  for (const f of files) {
    const buf = fs.readFileSync(path.join(dir, f));
    const { params, verbas, verbasPrincipais } = await C.parsePJC(buf, JSZip, DOMParser);
    const r = C.grade(params, verbas, gab, verbasPrincipais);
    const div = r.boletim.filter(b => b.status !== 'OK').map(b => b.key);
    console.log(`  ${f.padEnd(30)} nota=${r.notaCalculo.toFixed(1).padStart(4)}  ${r.pesoOk}/${r.pesoTot}  div: ${div.join(', ') || '-'}`);
  }
})().catch(e => { console.error('ERRO', e); process.exit(1); });
