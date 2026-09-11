// Ponte com a Ordem dos Calculistas do Brasil.
//
// Se o aluno informar o e-mail do cadastro dele na Ordem, o .PJC que ele acabou
// de enviar aqui é mandado (de novo, em bytes brutos) para a Edge Function da
// Ordem, que CORRIGE O ARQUIVO DO ZERO do lado de lá antes de decidir se
// concede a insígnia "Impugnação Correta". A nota que este app mostrou na tela
// não é o que decide — é só o que o aluno vê primeiro.
//
// Sem e-mail preenchido, nada é enviado: a correção normal do app continua
// funcionando exatamente igual para quem não é da Ordem.
(function () {
  "use strict";

  function getConfig() {
    return window.OCB_INSIGNIA_CONFIG || {};
  }

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function ensureCard() {
    let card = document.getElementById("card-ocb-insignia");
    if (card) return card;

    card = document.createElement("div");
    card.className = "card";
    card.id = "card-ocb-insignia";
    card.style.display = "none";
    card.innerHTML = `
      <h2>Ordem dos Calculistas do Brasil</h2>
      <div id="ocb-insignia-body" style="font-size:13.5px;color:var(--text-soft);"></div>
    `;
    const anchor = document.getElementById("card-cta");
    if (anchor?.parentNode) anchor.parentNode.insertBefore(card, anchor);
    return card;
  }

  function corpo(html) {
    ensureCard().style.display = "";
    const el = document.getElementById("ocb-insignia-body");
    if (el) el.innerHTML = html;
  }

  // .PJC é pequeno (dezenas/centenas de KB) — laço em blocos evita estourar a
  // pilha do spread operator em arquivo grande.
  function paraBase64(bytes) {
    let binario = "";
    const BLOCO = 0x8000;
    for (let i = 0; i < bytes.length; i += BLOCO) {
      binario += String.fromCharCode.apply(null, bytes.subarray(i, i + BLOCO));
    }
    return btoa(binario);
  }

  /**
   * @param {{exercicio:string, email:string, filePjc:File, impugnacaoTexto?:string}} args
   */
  async function registrar({ exercicio, email, filePjc, impugnacaoTexto }) {
    const config = getConfig();
    const emailLimpo = String(email || "").trim();

    if (!emailLimpo) return null; // aluno não informou e-mail: nada a fazer, sem erro
    if (!config.enabled || !config.functionUrl) return null;
    if (!filePjc) return null;

    corpo("Conferindo com a Ordem…");

    try {
      const bytes = new Uint8Array(await filePjc.arrayBuffer());
      const pjcBase64 = paraBase64(bytes);

      const headers = { "Content-Type": "application/json" };
      if (config.publishableKey) {
        headers.apikey = config.publishableKey;
        headers.Authorization = `Bearer ${config.publishableKey}`;
      }

      const response = await fetch(config.functionUrl, {
        method: "POST",
        headers,
        body: JSON.stringify({
          exercicio,
          email: emailLimpo,
          pjcBase64,
          impugnacaoTexto: impugnacaoTexto || "",
        }),
      });

      let payload = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }

      if (!response.ok) {
        const msg = payload?.erro || `HTTP ${response.status}`;
        throw new Error(msg);
      }

      if (payload?.concedido) {
        corpo(
          `<div class="diff diff-ok" style="display:inline-block;margin-bottom:8px;">Insígnia concedida</div>` +
            `<p>Você já soma <b>${esc(payload.quantidade)}</b> impugnação(ões) certeira(s) no quadro da Ordem. ` +
            `Nota do cálculo aferida pela Ordem: ${esc(payload.notaCalculo)} · cobertura: ${esc(payload.notaCobertura)}%.</p>`
        );
      } else if (payload?.ja_tinha) {
        corpo(
          `<p>Este exercício já tinha crédito para o seu e-mail — o crédito é um por exercício, ` +
            `mesmo reenviando. Você continua com <b>${esc(payload.quantidade)}</b> impugnação(ões) certeira(s).</p>`
        );
      } else if (payload?.motivo === "email_nao_encontrado") {
        corpo(
          `<p>Não encontrei este e-mail no cadastro da Ordem. Confira se é o mesmo da sua conta na Curseduca ` +
            `— se for, é só continuar: o crédito fica registrado assim que a correção passar do limiar.</p>`
        );
      } else if (payload?.motivo === "criterio_nao_atingido") {
        corpo(
          `<p>Esta correção ainda não passou do limiar da Ordem (nota do cálculo ≥ 8 e cobertura da impugnação ≥ 80%). ` +
            `Continue revisando e reenvie — a nota mostrada acima já indica onde ajustar.</p>`
        );
      } else {
        corpo(`<p>Não consegui registrar na Ordem desta vez. Tente reenviar.</p>`);
      }

      return payload;
    } catch (error) {
      console.warn("Registro na Ordem indisponível:", error);
      corpo(
        `<p>Não consegui falar com a Ordem agora. Sua nota e boletim acima continuam válidos — ` +
          `se você é membro, pode tentar reenviar mais tarde.</p>`
      );
      return null;
    }
  }

  function resetar() {
    const card = document.getElementById("card-ocb-insignia");
    if (card) card.style.display = "none";
  }

  window.OcbInsignia = { registrar, resetar };
})();
