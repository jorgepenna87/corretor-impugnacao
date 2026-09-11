// Ponte com a Ordem dos Calculistas do Brasil: quem resolve um exercício
// corretamente aqui ganha a insígnia "Impugnação Correta" no quadro da Ordem.
//
// A chave abaixo NÃO é segredo — é a "publishable key" do Supabase da Ordem,
// feita para viajar em JavaScript público (o mesmo padrão de ai-config.js
// acima). O que protege a insígnia é a Edge Function corrigir o .PJC de novo,
// do lado de lá, antes de conceder — não uma chave escondida aqui.
window.OCB_INSIGNIA_CONFIG = {
  enabled: true,
  functionUrl: "https://oauigtmxsonyhcfcspsu.supabase.co/functions/v1/conceder-impugnacao",
  publishableKey: "sb_publishable_-cd2p4WeZQdnYrgny9UyAA_ghUH8mQp",
};
