import fs from "node:fs/promises";

const configPath = new URL("../app/ai-config.js", import.meta.url);
const configSource = await fs.readFile(configPath, "utf8");

const urlMatch = configSource.match(/functionUrl\s*:\s*["']([^"']+)["']/);
if (!urlMatch?.[1]) {
  throw new Error("Não foi possível localizar functionUrl em app/ai-config.js.");
}

const functionUrl = urlMatch[1];
const basePayload = {
  exercicio: "marco16",
  texto: "abc",
  resultadoDeterministico: {
    notaCalculo: 0,
    notaCobertura: 0,
    itensRever: [],
    temas: [],
  },
};

async function request(origin) {
  const headers = {
    "Content-Type": "application/json",
  };

  if (origin) headers.Origin = origin;

  const response = await fetch(functionUrl, {
    method: "POST",
    headers,
    body: JSON.stringify(basePayload),
  });

  let body = null;
  try {
    body = await response.json();
  } catch {
    body = { error: "Resposta não JSON" };
  }

  return { status: response.status, body };
}

function assertStatus(label, actual, expected) {
  if (actual.status !== expected) {
    throw new Error(
      `${label}: esperado HTTP ${expected}, recebido HTTP ${actual.status}. ` +
        `Resposta: ${JSON.stringify(actual.body)}`,
    );
  }

  console.log(`OK: ${label} → HTTP ${expected}`);
}

const withoutOrigin = await request(null);
assertStatus("requisição sem Origin é bloqueada", withoutOrigin, 403);

const invalidOrigin = await request("https://site-estranho.example");
assertStatus("origem não autorizada é bloqueada", invalidOrigin, 403);

const allowedOrigin = await request("http://localhost:8000");
assertStatus(
  "origem permitida passa pela segurança e para na validação do texto",
  allowedOrigin,
  400,
);

console.log("\nTeste real de segurança do endpoint concluído sem chamar a OpenAI.");

