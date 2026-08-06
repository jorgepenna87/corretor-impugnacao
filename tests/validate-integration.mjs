import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.argv[2] ? path.resolve(process.argv[2]) : process.cwd();
const required = [
  "app/ai-config.js",
  "app/ai-feedback.js",
  "supabase/functions/analisar-impugnacao/index.ts",
  "supabase/migrations/202608060001_ai_request_log.sql",
];

let failed = false;
for (const relative of required) {
  const full = path.join(root, relative);
  if (!fs.existsSync(full)) {
    console.error(`FALTANDO: ${relative}`);
    failed = true;
  } else {
    console.log(`OK: ${relative}`);
  }
}

const configPath = path.join(root, "app/ai-config.js");
if (fs.existsSync(configPath)) {
  const config = fs.readFileSync(configPath, "utf8");
  if (/sk-[A-Za-z0-9_-]{10,}/.test(config)) {
    console.error("SEGREDO EXPOSTO: parece haver uma chave OpenAI em app/ai-config.js");
    failed = true;
  } else {
    console.log("OK: nenhuma chave OpenAI aparente no frontend");
  }
}

if (failed) process.exit(1);
console.log("\nValidação estrutural concluída.");
