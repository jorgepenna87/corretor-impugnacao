(function () {
  "use strict";

  const MAX_TEXT_CHARS = 40_000;

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getConfig() {
    return window.CORRETOR_AI_CONFIG || {};
  }

  function ensureCard() {
    let card = document.getElementById("card-ai-feedback");
    if (card) return card;

    card = document.createElement("div");
    card.className = "card";
    card.id = "card-ai-feedback";
    card.style.display = "none";
    card.innerHTML = `
      <h2>Análise pedagógica por IA <span class="beta-tag">beta</span></h2>
      <p style="font-size:12.5px;color:var(--text-soft);margin-bottom:10px;">
        A IA avalia clareza, fundamentação e qualidade argumentativa. Ela não altera a nota do cálculo nem substitui o motor determinístico.
      </p>
      <div id="ai-feedback-status" style="font-size:13px;color:var(--text-soft);"></div>
      <div id="ai-feedback-body"></div>
    `;

    const anchor = document.getElementById("card-diagnostico") || document.getElementById("card-cta");
    if (anchor?.parentNode) anchor.parentNode.insertBefore(card, anchor);
    return card;
  }

  function setStatus(message) {
    ensureCard();
    const el = document.getElementById("ai-feedback-status");
    if (el) el.textContent = message || "";
  }

  function renderList(title, items) {
    if (!Array.isArray(items) || !items.length) return "";
    return `
      <div style="margin-top:14px;">
        <strong>${esc(title)}</strong>
        <ul style="margin:8px 0 0 18px;">
          ${items.map((item) => `<li style="margin-bottom:6px;">${esc(item)}</li>`).join("")}
        </ul>
      </div>
    `;
  }

  function render(data) {
    const card = ensureCard();
    const body = document.getElementById("ai-feedback-body");
    card.style.display = "";
    setStatus("");

    const score = Number.isFinite(Number(data.notaQualidade))
      ? Math.max(0, Math.min(100, Number(data.notaQualidade)))
      : null;

    const scoreHtml = score == null
      ? ""
      : `<div style="display:flex;align-items:center;gap:12px;margin:12px 0;">
           <div class="nota-badge ${score >= 80 ? "alto" : score >= 50 ? "medio" : "baixo"}">${score}%</div>
           <div><strong>Qualidade argumentativa</strong><br><span style="font-size:12.5px;color:var(--text-soft);">Avaliação complementar, sem impacto na nota determinística.</span></div>
         </div>`;

    body.innerHTML = `
      ${scoreHtml}
      <p style="line-height:1.6;">${esc(data.resumo || "Análise concluída.")}</p>
      ${renderList("Pontos fortes", data.pontosFortes)}
      ${renderList("O que melhorar", data.pontosMelhorar)}
      ${renderList("Próximos passos", data.proximosPassos)}
      ${data.observacao ? `<div class="aviso-box" style="margin-top:14px;">${esc(data.observacao)}</div>` : ""}
    `;
  }

  function renderUnavailable(message) {
    const card = ensureCard();
    const body = document.getElementById("ai-feedback-body");
    card.style.display = "";
    setStatus("");
    body.innerHTML = `<div class="aviso-box">${esc(message)}</div>`;
  }

  function sanitizeDeterministic(resultado, resultadoText) {
    const boletim = Array.isArray(resultado?.boletim) ? resultado.boletim : [];
    const cobertura = Array.isArray(resultadoText?.cobertura) ? resultadoText.cobertura : [];

    return {
      notaCalculo: Number.isFinite(Number(resultado?.notaCalculo)) ? Number(resultado.notaCalculo) : null,
      notaCobertura: Number.isFinite(Number(resultadoText?.notaImpugnacao))
        ? Number(resultadoText.notaImpugnacao)
        : null,
      itensRever: boletim
        .filter((item) => item && item.status !== "OK")
        .slice(0, 40)
        .map((item) => ({
          dimensao: Number(item.dimensao) || null,
          label: String(item.label || "Item a revisar").slice(0, 180),
          status: String(item.status || "REVER").slice(0, 20),
        })),
      temas: cobertura.slice(0, 30).map((item) => ({
        tema: String(item.tema || "Tema").slice(0, 180),
        coberto: Boolean(item.coberto),
      })),
    };
  }

  async function analisar({ exercicio, textoImpug, resultado, resultadoText }) {
    const config = getConfig();
    const card = ensureCard();

    if (!textoImpug || !String(textoImpug).trim()) {
      card.style.display = "none";
      return null;
    }

    if (!config.enabled || !config.functionUrl || config.functionUrl.includes("SEU_PROJECT_REF")) {
      card.style.display = "none";
      return null;
    }

    const text = String(textoImpug).trim().slice(0, MAX_TEXT_CHARS);
    card.style.display = "";
    document.getElementById("ai-feedback-body").innerHTML = "";
    setStatus("Gerando análise pedagógica…");

    const headers = { "Content-Type": "application/json" };
    if (config.publishableKey) {
      headers.apikey = config.publishableKey;
      headers.Authorization = `Bearer ${config.publishableKey}`;
    }

    try {
      const response = await fetch(config.functionUrl, {
        method: "POST",
        headers,
        body: JSON.stringify({
          exercicio,
          texto: text,
          resultadoDeterministico: sanitizeDeterministic(resultado, resultadoText),
        }),
      });

      let payload = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }

      if (!response.ok) {
        const msg = payload?.error || `Falha na análise por IA (HTTP ${response.status}).`;
        throw new Error(msg);
      }

      render(payload);
      return payload;
    } catch (error) {
      console.warn("Análise pedagógica por IA indisponível:", error);
      renderUnavailable(
        "A análise por IA ficou indisponível nesta tentativa. A nota e o boletim determinísticos continuam válidos."
      );
      return null;
    }
  }

  function resetar() {
    const card = document.getElementById("card-ai-feedback");
    if (!card) return;
    card.style.display = "none";
    const body = document.getElementById("ai-feedback-body");
    if (body) body.innerHTML = "";
    setStatus("");
  }

  window.CorretorAI = { analisar, resetar };
})();
