# -*- coding: utf-8 -*-
"""
comparar_calculos.py — analise MINUCIOSA e diff de dois calculos PJe-Calc.

Le um calculo (relatorio PDF via parse_pjecalc, OU o .PJC/XML), normaliza para uma
estrutura canonica verba-a-verba (valor historico, corrigido, juros, pago, base,
multiplicador, divisor, quantidade, integracoes) e COMPARA dois calculos, retornando
TODOS os pontos onde ha diferenca.

Uso:
    python comparar_calculos.py CALC_A CALC_B            # relatorio de diferencas
    python comparar_calculos.py CALC_A CALC_B --json     # saida JSON
    python comparar_calculos.py CALC_A                   # so imprime a analise de A

Aceita .pdf (relatorio PJe-Calc) e .pjc/.xml. NAO recalcula nada — le os valores que
o PJe-Calc ja computou e os compara. Reusa o parse_pjecalc (ja endurecido por autoresearch).
"""
from __future__ import annotations
import difflib
import json
import sys
import unicodedata
import zipfile
from pathlib import Path

# parse_pjecalc (parser endurecido do relatorio PDF)
_PARSER_DIR = Path(r"C:\Users\jorge\Documents\CLAUDE\AutoResearch-Skills\ler-pjecalc-txt\scripts")
if _PARSER_DIR.exists():
    sys.path.insert(0, str(_PARSER_DIR))

TOL = 0.01       # 1 centavo — analise minuciosa (valores monetarios)
TOL_ALIQ = 1e-6  # aliquotas em FRACAO (0.08): tolerancia de 1 centavo esconderia quase 1 ponto


# ───────────────────────── util ─────────────────────────
def _norm(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.upper().split())


import re as _re

# stopwords/numeracao que NAO ajudam a distinguir verba
_STOP = {"SOBRE", "DA", "DE", "DO", "DOS", "DAS", "E", "A", "O", "AO", "NA", "NO", "CLT",
         "ARTIGO", "ART", "SEMANAL"}


def _tokens_verba(nome):
    limpo = _re.sub(r"[^A-Z0-9 ]", " ", _norm(nome))
    return {t for t in limpo.split() if len(t) >= 3 and t not in _STOP and not t.isdigit()}


def _prefixo_comum(t1, t2):
    n = 0
    for c1, c2 in zip(t1, t2):
        if c1 != c2:
            break
        n += 1
    return n


def _tok_match(t1, t2):
    return t1 == t2 or _prefixo_comum(t1, t2) >= 5  # plural/variacao (DIFERENCA/DIFERENCAS)


def _sim_nome(a, b):
    """Similaridade de nome de verba (0..1). Casa 'mesma verba, nome ligeiramente
    diferente' (DIFERENCA SALARIAL x DIFERENCAS SALARIAIS (EQUIPARACAO); AVISO PREVIO
    x AVISO PREVIO INDENIZADO) sem casar verbas distintas."""
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return 1.0
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = _tokens_verba(a), _tokens_verba(b)
    if ta and tb:
        menor, maior = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
        casados = sum(1 for x in menor if any(_tok_match(x, y) for y in maior))
        overlap = casados / max(len(ta), len(tb))
        # subconjunto: TODOS os tokens do menor casam E o menor tem >=2 tokens -> mesma verba
        if len(menor) >= 2 and casados == len(menor):
            overlap = max(overlap, 0.85)
        ratio = max(ratio, overlap)
    return ratio


def _sig_estrutural(w):
    """O que a verba FAZ (independe do nome): tipo, se pega base+pago (diferenca de
    duas bases = diferenca salarial), quantos meses, ordem de grandeza da base."""
    return {
        "tipo": w.get("tipo"),
        "diferenca_2bases": (w.get("valor_pago") or 0) > 0.01 and (w.get("base_total") or 0) > 0.01,
        "n_meses": len(w.get("meses") or []),
        "base": w.get("base_total"),
    }


def _sim_verba(wa, wb):
    """Similaridade INTELIGENTE = nome + ESTRUTURA (o que a verba faz). Reconhece a
    mesma verba mesmo com nome bem diferente pela funcao dela — ex.: duas verbas que
    pegam base(paradigma)+pago(reclamante) e apuram a diferenca salarial sao a mesma."""
    # reflexo e verba PROPRIA sao especies distintas: '13o SOBRE X' contem os tokens
    # de 'X' e empataria com a propria principal X — nunca casar entre especies
    if wa.get("tipo") != wb.get("tipo"):
        return min(_sim_nome(wa["nome"], wb["nome"]), 0.60)
    sn = _sim_nome(wa["nome"], wb["nome"])
    if sn >= 0.80:
        return sn
    sa, sb = _sig_estrutural(wa), _sig_estrutural(wb)
    pts = tot = 0.0
    tot += 1.0; pts += 1.0 if sa["tipo"] == sb["tipo"] else 0.0
    tot += 2.0; pts += 2.0 if sa["diferenca_2bases"] == sb["diferenca_2bases"] else 0.0
    if sa["n_meses"] and sb["n_meses"]:
        tot += 1.0; pts += 1.0 if abs(sa["n_meses"] - sb["n_meses"]) <= 2 else 0.0
    if sa["base"] and sb["base"]:
        tot += 1.0; pts += 1.0 if 0.4 <= abs(sa["base"]) / abs(sb["base"]) <= 2.5 else 0.0
    est = pts / tot if tot else 0.0
    # dif2bases (pega base paradigma + pago reclamante) e DISTINTIVO -> estrutura forte
    # basta, mesmo com nome bem diferente (a "inteligencia" que reconhece a mesma verba).
    if est >= 0.95 and sa["diferenca_2bases"] and sb["diferenca_2bases"]:
        return max(sn, 0.82)
    # outros tipos: estrutura forte SO decide se o nome nao for claramente outra verba
    if est >= 0.95 and sn >= 0.45:
        return max(sn, 0.82)
    return sn


def _f(x):
    try:
        return float(x) if x not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None


def _difere(a, b, tol=TOL):
    if a is None and b is None:
        return False
    if a is None or b is None:
        return True
    return abs(a - b) > tol


def _vazio(x):
    return x is None or (isinstance(x, str) and x.strip() in ("", "null"))


def _difere_any(a, b, tol=TOL):
    """Diferenca numerica (com tolerancia) OU textual (config: indice, incidencia, on/off).
    Vazio (None, "", "null") nunca difere de outro vazio."""
    if _vazio(a) and _vazio(b):
        return False
    if _vazio(a) or _vazio(b):
        return True
    fa, fb = _f(a), _f(b)
    if fa is not None and fb is not None:
        return abs(fa - fb) > tol
    return str(a).strip() != str(b).strip()


def _fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(v)


# vocabularios diferentes p/ o MESMO indice/juros (XML do .PJC x relatorio PDF)
_CANON_INDICE = {
    "IPCAE": "IPCA-E", "IPCA E": "IPCA-E",
    "TRD SIMPLES": "SIMPLES TRD",
}


def _indice_canon(s):
    """Nome canonico de indice/juros — 'IPCAE' (XML) == 'IPCA-E' (PDF) etc."""
    if _vazio(s):
        return None
    n = " ".join(_norm(s).replace("_", " ").replace("-", " ").split())
    return _CANON_INDICE.get(n, n)


_RE_COMP = _re.compile(r"(\d{2})/(\d{4})\s*$")


def _competencia_de_periodo(p):
    """'01 a 31/03/2021' -> '03/2021' (competencia p/ casar mes-a-mes)."""
    m = _RE_COMP.search(str(p or ""))
    return f"{m.group(1)}/{m.group(2)}" if m else None


def _epoch_data(ms):
    """Epoch ms (XML do PJC) -> datetime.date, ou None."""
    if not ms or ms == "null":
        return None
    try:
        import datetime
        return datetime.datetime.fromtimestamp(int(ms) / 1000, datetime.timezone.utc).date()
    except (ValueError, OSError):
        return None


def _iso_menos_1d(iso):
    try:
        import datetime
        return (datetime.date.fromisoformat(iso) - datetime.timedelta(days=1)).isoformat()
    except (TypeError, ValueError):
        return iso


def _pareia_meses(ma, mb):
    """Casa mes-a-mes por COMPETENCIA (mm/aaaa) quando ambos os lados a tem em todos
    os meses; senao cai pra ordem (fallback). Retorna (pares, so_a, so_b) — meses sem
    par sao ERRO DE PERIODO real, nao entram em comparacao cega por indice."""
    ma, mb = list(ma or []), list(mb or [])
    if not ma or not mb:
        return [], ma, mb
    if any(not m.get("competencia") for m in ma) or any(not m.get("competencia") for m in mb):
        n = min(len(ma), len(mb))
        return list(zip(ma, mb)), ma[n:], mb[n:]
    ga, gb = {}, {}
    for m in ma:
        ga.setdefault(m["competencia"], []).append(m)
    for m in mb:
        gb.setdefault(m["competencia"], []).append(m)

    def _k(c):
        mm, aa = c.split("/")
        return (int(aa), int(mm))

    def _casa_grupo(la, lb):
        # 2+ ocorrencias na MESMA competencia (13o integral + proporcional): casa por
        # PROXIMIDADE DE VALORES, nao pela ordem — reordenacao interna nao e erro
        if len(la) <= 1 and len(lb) <= 1:
            n = min(len(la), len(lb))
            return list(zip(la, lb)), la[n:], lb[n:]

        def dist(x, y):
            return sum(abs((x.get(k) or 0.0) - (y.get(k) or 0.0))
                       for k in ("base", "devido", "pago", "quantidade", "diferenca"))

        cand = sorted(((dist(x, y), i, j) for i, x in enumerate(la) for j, y in enumerate(lb)),
                      key=lambda t: t[0])
        usa, usb, pr = set(), set(), []
        for _, i, j in cand:
            if i in usa or j in usb:
                continue
            usa.add(i)
            usb.add(j)
            pr.append((la[i], lb[j]))
        return (pr, [x for i, x in enumerate(la) if i not in usa],
                [y for j, y in enumerate(lb) if j not in usb])

    pares, so_a, so_b = [], [], []
    for comp in sorted(set(ga) | set(gb), key=_k):
        pr, sa, sb = _casa_grupo(ga.get(comp, []), gb.get(comp, []))
        pares += pr
        so_a += sa
        so_b += sb
    return pares, so_a, so_b


# ───────────────────────── canonico ─────────────────────────
def _verba_tipo(nome):
    return "reflexo" if "SOBRE" in (nome or "").upper() else "principal"


def _canonico_de_parse(d):
    """Normaliza a saida do parse_pjecalc (dict) para a estrutura canonica."""
    verbas = {}
    # 1) resumo -> valor_corrigido, juros, total por verba
    for v in d.get("resumo", []) or []:
        nome = v.get("nome") or v.get("descricao")
        if not nome:
            continue
        k = _norm(nome)
        verbas[k] = {
            "nome": nome, "tipo": _verba_tipo(nome),
            "valor_corrigido": _f(v.get("valor_corrigido")),
            "valor_juros": _f(v.get("juros")),
            "valor_total": _f(v.get("total")),
            "valor_historico": None, "valor_pago": None, "base_total": None,
            "formula": None, "meses": [],
        }
    # 2) demonstrativos -> historico/pago/base + meses (base, div, mult, qtd, devido, pago, dif, corrigido)
    for dm in d.get("demonstrativos", []) or []:
        nome = dm.get("nome")
        if not nome:
            continue
        k = _norm(nome)
        vb = verbas.setdefault(k, {
            "nome": nome, "tipo": _verba_tipo(nome),
            "valor_corrigido": None, "valor_juros": None, "valor_total": _f(dm.get("total")),
            "valor_historico": None, "valor_pago": None, "base_total": None,
            "formula": None, "meses": [],
        })
        vb["formula"] = dm.get("formula")
        meses = []
        s_dif = s_pago = s_base = s_dev = 0.0
        for m in dm.get("meses", []) or []:
            reg = {kk: _f(m.get(kk)) for kk in
                   ["base", "divisor", "multiplicador", "quantidade", "devido", "pago", "diferenca", "valor_corrigido"]}
            reg["periodo"] = m.get("periodo")
            reg["competencia"] = _competencia_de_periodo(m.get("periodo"))
            meses.append(reg)
            s_dif += reg["diferenca"] or 0.0
            s_pago += reg["pago"] or 0.0
            s_base += reg["base"] or 0.0
            s_dev += reg["devido"] or 0.0
        vb["meses"] = meses
        vb["valor_historico"] = round(s_dif, 2)      # valor historico apurado (nominal, sem correcao)
        vb["valor_pago"] = round(s_pago, 2)
        vb["base_total"] = round(s_base, 2)
        vb["valor_devido"] = round(s_dev, 2)
    meta = {k: d.get(k) for k in
            ["arquivo", "processo", "calculo_id", "reclamante", "reclamado",
             "periodo_inicio", "periodo_fim", "data_ajuizamento", "versao_pjecalc"]}
    meta["fonte"] = "pdf"
    return {
        "meta": meta,
        "verbas": verbas,
        "bases_calculo": d.get("bases_calculo") or {},
        "contribuicoes": d.get("contribuicoes") or {},
        "criterio_indices": [{**c, "indice": _indice_canon(c.get("indice"))}
                             for c in (d.get("criterio_indices") or [])],
        "criterio_juros": [{**c, "tipo": _indice_canon(c.get("tipo"))}
                           for c in (d.get("criterio_juros") or [])],
        "config_juros": {},
        "cartao": {"config": {}, "dias": {}},   # o relatorio PDF nao traz a apuracao do cartao
        "seguro_desemprego": {},
        "totais": {k: _f(d.get(k)) for k in
                   ["total_devido_reclamado", "liquido_devido_reclamante"]},
        "totais_resumo": d.get("totais_resumo") or {},
    }


def _canonico_de_pjc(path):
    """Le o .PJC (ZIP+XML) e normaliza para a mesma estrutura canonica.

    Le as ocorrencias DIRETAS de cada verba (ocorrencias/List/OcorrenciaDeVerba) —
    base/devido/pago/diferenca por mes; juros/corrigido das apuracoesDeJuros."""
    import xml.etree.ElementTree as ET
    z = zipfile.ZipFile(path)
    xml = z.read(z.namelist()[0]).decode("iso-8859-1")
    root = ET.fromstring(xml)

    def txt(el, t):
        c = el.find(t)
        return c.text if c is not None and c.text else None

    verbas = {}
    vroot = root.find(".//verbas")
    if vroot is not None:
        for el in vroot.iter():
            if el.tag not in ("Calculada", "Reflexo"):
                continue
            # 'nome' e o COMPOSTO ('13o SALARIO SOBRE DIFERENCA SALARIAL' — igual ao PDF);
            # 'descricao' e ambigua entre principais. Verba inativa nao sai no relatorio.
            desc = txt(el, "nome") or txt(el, "descricao")
            if not desc:
                continue
            if txt(el, "ativo") == "false":
                continue
            k = _norm(desc)
            occ = el.find("ocorrencias")
            meses = []
            s_dif = s_pago = s_base = s_dev = 0.0
            if occ is not None:
                lst = occ.find("List")
                for o in (lst if lst is not None else []):
                    if o.tag != "OcorrenciaDeVerba":
                        continue
                    base = _f(o.findtext("base")); dev = _f(o.findtext("devido"))
                    pago = _f(o.findtext("pago")); div = _f(o.findtext("divisor"))
                    mult = _f(o.findtext("multiplicador")); qtd = _f(o.findtext("quantidade"))
                    di = _epoch_data(o.findtext("dataInicial"))
                    dfim = _epoch_data(o.findtext("dataFinal"))
                    periodo = (f"{di.day:02d} a {dfim.day:02d}/{dfim.month:02d}/{dfim.year}"
                               if di and dfim else None)
                    comp = f"{dfim.month:02d}/{dfim.year}" if dfim else None
                    dif = (dev or 0.0) - (pago or 0.0)
                    meses.append({"periodo": periodo, "competencia": comp, "base": base,
                                  "divisor": div, "multiplicador": mult, "quantidade": qtd,
                                  "devido": dev, "pago": pago, "diferenca": round(dif, 2),
                                  "valor_corrigido": None})
                    s_dif += dif; s_pago += pago or 0.0; s_base += base or 0.0; s_dev += dev or 0.0
            # config PROPRIA da verba (inputs que o aluno marca na tela de verbas)
            cfg = {}
            for tag, rot in [("incidenciaINSS", "incidencia INSS"),
                             ("incidenciaFGTS", "incidencia FGTS"),
                             ("incidenciaIRPF", "incidencia IRPF"),
                             ("aplicarProporcionalidade", "proporcionalidade"),
                             ("zeraValorNegativo", "zera valor negativo")]:
                tv = txt(el, tag)
                if tv is not None:
                    cfg[rot] = tv
            piv, pfv = txt(el, "periodoInicial"), txt(el, "periodoFinal")
            if piv or pfv:
                dpi, dpf = _epoch_data(piv), _epoch_data(pfv)
                cfg["periodo da verba"] = (f"{dpi.isoformat() if dpi else '?'} a "
                                           f"{dpf.isoformat() if dpf else '?'}")
            verbas[k] = {
                "nome": desc, "tipo": ("reflexo" if el.tag == "Reflexo" else "principal"),
                "valor_corrigido": None, "valor_juros": None, "valor_total": None,
                "valor_historico": round(s_dif, 2), "valor_pago": round(s_pago, 2),
                "base_total": round(s_base, 2), "valor_devido": round(s_dev, 2),
                "formula": None, "meses": meses, "config": cfg or None,
            }
    # config/parametros (o que as mudancas de aliquota/FGTS/INSS/indice/custas tocam)
    def first(tag):
        for e in root.iter(tag):
            return e.text
        return None

    def epoch_iso(ms):
        if not ms or ms == "null":
            return None
        try:
            import datetime
            return datetime.datetime.fromtimestamp(int(ms) / 1000, datetime.timezone.utc).date().isoformat()
        except (ValueError, OSError):
            return ms

    # criterio de indices: 1o indice ate a vespera do divisor, 2o indice a partir dele
    # (mesma convencao do relatorio PDF: ate=vespera / de=data da troca)
    comb = (first("combinarOutroIndice") or "false") == "true"
    div = epoch_iso(first("apartirDeOutroIndice"))
    if comb and div:
        criterio_indices = [
            {"de": None, "ate": _iso_menos_1d(div), "indice": _indice_canon(first("indiceTrabalhista"))},
            {"de": div, "ate": None, "indice": _indice_canon(first("outroIndiceTrabalhista"))},
        ]
    else:
        criterio_indices = [{"de": None, "ate": None, "indice": _indice_canon(first("indiceTrabalhista"))}]

    # criterio de juros (mesma estrutura do PDF) + config fina de juros (so o .PJC expoe)
    combj = (first("combinarOutroJuros") or "false") == "true"
    divj = epoch_iso(first("apartirDeOutroJuros"))
    if combj and divj:
        criterio_juros = [
            {"de": None, "ate": _iso_menos_1d(divj), "tipo": _indice_canon(first("juros"))},
            {"de": divj, "ate": None, "tipo": _indice_canon(first("outroJuros"))},
        ]
    else:
        criterio_juros = [{"de": None, "ate": None, "tipo": _indice_canon(first("juros"))}]
    config_juros = {
        "aplicar fase pre-judicial": first("aplicarJurosFasePreJudicial"),
        "juros do ajuizamento": first("jurosDoAjuizamento"),
        "base de juros das verbas": first("baseDeJurosDasVerbas"),
        "juros de custas": first("jurosDeCustas"),
    }

    # FGTS: soma das bases do bloco <fgts> + config
    fgts_base = 0.0
    for f_el in root.iter("Fgts"):
        b = _f(f_el.findtext("base"))
        if b:
            fgts_base += b
    bases_calculo = {
        "fgts": {"base_total": round(fgts_base, 2) if fgts_base else None,
                 "aliquota": first("fgtsAliquota"), "multa": first("multaDoFgts"),
                 "incidencia": first("incidenciaDoFgts"),
                 "indice_correcao": first("indiceDeCorrecaoDoFGTS")},
        "irpf": {"apurar": first("apurarImpostoRenda")},
    }

    # ── cartao de ponto: config da apuracao (D6) + apuracao diaria (D6/D9) ──
    # config: Calculo > apuracoesCartaoDePonto > ... > ApuracaoCartaoDePonto (escalares)
    # dias:   Calculo > apuracoesDiariasCartaoDePonto > Set > ApuracaoDiariaCartao
    # (caminhos DIRETOS — root.iter pegaria as copias do grafo XStream)
    cartao = {"config": {}, "dias": {}}
    cont_cfg = root.find("apuracoesCartaoDePonto")
    if cont_cfg is not None:
        ap = next(cont_cfg.iter("ApuracaoCartaoDePonto"), None)
        if ap is not None:
            for c in ap:
                if len(list(c)) == 0 and c.tag not in ("id", "versao"):
                    cartao["config"][c.tag] = (c.text or "").strip() or None
    cont_dias = root.find("apuracoesDiariasCartaoDePonto")
    if cont_dias is not None:
        for dset in cont_dias:
            for dd in dset:
                if dd.tag != "ApuracaoDiariaCartao":
                    continue
                dt = _epoch_data(dd.findtext("dataOcorrencia"))
                if dt is None:
                    continue
                reg = {}
                freq = (dd.findtext("frequenciaDiaria") or "").strip()
                if freq and freq != "null":
                    reg["frequencia"] = freq
                for c in dd:
                    if c.tag.startswith(("horas", "qt")) and len(list(c)) == 0:
                        v = _f(c.text)
                        if v:  # so o que nao e zero (ausente == 0.0 no diff)
                            reg[c.tag] = v
                if reg:
                    cartao["dias"][dt.isoformat()] = reg

    # ── seguro-desemprego (exercicios de rescisao; inputs do usuario + valor da parcela) ──
    seguro = {}
    sd = root.find("seguroDesemprego")
    sd_el = next(sd.iter("SeguroDesemprego"), None) if sd is not None else None
    if sd_el is not None and (sd_el.findtext("apurarSeguroDesemprego") or "false") == "true":
        seguro = {
            "apurar": sd_el.findtext("apurarSeguroDesemprego"),
            "tipo_solicitacao": sd_el.findtext("tipoSolicitacao"),
            "parcelas": _f(sd_el.findtext("numeroDeParcelas")),
            "tipo_salario": sd_el.findtext("tipoSalarioPago"),
            "remuneracao_mensal": _f(sd_el.findtext("remuneracaoMensal")),
            "empregado_domestico": sd_el.findtext("empregadoDomestico"),
            "valor_parcela": _f(sd_el.findtext("valorSeguroDesemprego")),   # computado
        }

    def _pct(x):
        # XML guarda aliquota em PONTOS (20.0); o PDF em FRACAO (0.20) — canonico = fracao
        v = _f(x)
        return round(v / 100.0, 6) if v is not None else None

    contribuicoes = {
        "empresa": {"aliquota": _pct(first("aliquotaEmpresaFixa"))},
        "sat_rat": {"aliquota": _pct(first("aliquotaRATFixa")),
                    "por_atividade": first("apurarRATPorAtividade")},
        "segurado": {"aliquota": _pct(first("aliquotaSegurado"))},
        "custas": {"devido": _f(first("valorConhecimentoDoReclamado")),
                   "tipo": first("tipoDeCustasDeConhecimentoDoReclamado")},
    }

    return {
        "meta": {"arquivo": Path(path).name, "fonte": "pjc",
                 "processo": None, "calculo_id": txt(root, "id"),
                 "versao_pjecalc": txt(root, "versaoDoSistema"),
                 "periodo_inicio": epoch_iso(first("dataAdmissao")),
                 "periodo_fim": epoch_iso(first("dataDemissao")),
                 "data_ajuizamento": epoch_iso(first("dataAjuizamento"))},
        "verbas": verbas, "bases_calculo": bases_calculo, "contribuicoes": contribuicoes,
        "criterio_indices": criterio_indices, "criterio_juros": criterio_juros,
        "config_juros": config_juros, "cartao": cartao, "seguro_desemprego": seguro,
        "totais": {}, "totais_resumo": {},
    }


def carregar(path):
    """Dispatch por extensao. .pdf -> parse_pjecalc; .pjc/.xml -> XML."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        import parse_pjecalc as P
        return _canonico_de_parse(P.to_dict(P.parse(p)))
    if ext in (".pjc", ".xml", ".zip"):
        return _canonico_de_pjc(p)
    raise ValueError(f"extensao nao suportada: {ext} (use .pdf ou .pjc)")


# ───────────────────────── diff ─────────────────────────
CAMPOS_VERBA = [
    ("valor_historico", "Valor historico apurado"),
    ("valor_corrigido", "Valor corrigido"),
    ("valor_juros", "Valor dos juros"),
    ("valor_total", "Valor total (corrigido+juros)"),
    ("valor_pago", "Valor pago"),
    ("base_total", "Base de calculo (total)"),
]
CAMPOS_MES = [
    ("base", "base de calculo"), ("multiplicador", "multiplicador"),
    ("divisor", "divisor"), ("quantidade", "quantidade"),
    ("devido", "devido"), ("pago", "pago"),
    ("diferenca", "diferenca"), ("valor_corrigido", "valor corrigido"),
]


# campos que so o PDF traz (computados) — no diff CRUZADO (pdf x pjc) nao comparam
_SO_PDF_VERBA = {"valor_corrigido", "valor_juros", "valor_total"}


def diff(a, b):
    out = {"meta": [], "verbas_so_a": [], "verbas_so_b": [], "verbas": [],
           "bases_calculo": [], "contribuicoes": [], "criterio": [], "totais": [],
           "nao_comparado": []}
    cross = (a["meta"].get("fonte") or "?") != (b["meta"].get("fonte") or "?")
    nao_comp = set()

    # verbas
    va, vb = a["verbas"], b["verbas"]

    def cmp_v(wa, wb):
        difs_campo = []
        for campo, rot in CAMPOS_VERBA:
            xa, xb = wa.get(campo), wb.get(campo)
            if cross and campo in _SO_PDF_VERBA and (xa is None or xb is None):
                if xa is not None or xb is not None:
                    nao_comp.add("verbas: valor corrigido/juros/total (so o PDF traz)")
                continue
            if _difere(xa, xb):
                difs_campo.append({"campo": rot, "a": xa, "b": xb,
                                   "delta": (None if xa is None or xb is None else round(xb - xa, 2))})
        # config propria da verba (incidencias, proporcionalidade, periodo da verba)
        cfa, cfb = wa.get("config"), wb.get("config")
        if cfa and cfb:
            for rot in sorted(set(cfa) | set(cfb)):
                if _difere_any(cfa.get(rot), cfb.get(rot)):
                    difs_campo.append({"campo": rot, "a": cfa.get(rot), "b": cfb.get(rot), "delta": None})
        elif (cfa or cfb) and cross:
            nao_comp.add("verbas: config (incidencias/proporcionalidade — so o .PJC traz)")
        difs_mes = []
        ma, mb = wa.get("meses") or [], wb.get("meses") or []
        if len(ma) != len(mb):
            difs_mes.append({"periodo": "(estrutura)", "campo": "qtd de meses", "a": len(ma), "b": len(mb)})
        pares, so_a, so_b = _pareia_meses(ma, mb)
        for x, y in pares:
            for campo, rot in CAMPOS_MES:
                xa, xb = x.get(campo), y.get(campo)
                if cross and (xa is None or xb is None):
                    if xa is not None or xb is not None:
                        nao_comp.add(f"meses: {rot} (ausente num dos formatos)")
                    continue
                if _difere(xa, xb):
                    difs_mes.append({"periodo": x.get("periodo") or y.get("periodo") or "?",
                                     "campo": rot, "a": xa, "b": xb})
        for m in so_a:
            difs_mes.append({"periodo": m.get("periodo") or "?", "campo": "mes so em A",
                             "a": m.get("diferenca"), "b": None})
        for m in so_b:
            difs_mes.append({"periodo": m.get("periodo") or "?", "campo": "mes so em B",
                             "a": None, "b": m.get("diferenca")})
        return difs_campo, difs_mes

    def registra(wa, wb, nota=None):
        dc, dm = cmp_v(wa, wb)
        if dc or dm:
            item = {"nome": wa["nome"], "tipo": wa["tipo"], "campos": dc, "meses": dm}
            if nota:
                item["obs"] = nota  # ex.: nome difere (mesma verba)
            out["verbas"].append(item)

    # 1) casamento EXATO por nome normalizado
    comuns = set(va) & set(vb)
    for k in sorted(comuns):
        registra(va[k], vb[k])
    resto_a = [k for k in va if k not in comuns]
    resto_b = [k for k in vb if k not in comuns]

    # 2) casamento FUZZY das nao-batidas (mesma verba, nome ligeiramente diferente)
    LIMIAR = 0.80
    pares = []
    for ka in resto_a:
        for kb in resto_b:
            s = _sim_verba(va[ka], vb[kb])   # nome + estrutura (o que a verba faz)
            if s >= LIMIAR:
                pares.append((s, ka, kb))
    pares.sort(reverse=True, key=lambda x: x[0])
    usados_a, usados_b = set(), set()
    for s, ka, kb in pares:
        if ka in usados_a or kb in usados_b:
            continue
        usados_a.add(ka); usados_b.add(kb)
        nota = None if _norm(va[ka]["nome"]) == _norm(vb[kb]["nome"]) else f"nome difere de B: '{vb[kb]['nome']}'"
        registra(va[ka], vb[kb], nota)

    # 3) sobrou = verba genuinamente so em A / so em B (erro real de presenca).
    # No CRUZADO, FGTS-verba e representacao do PDF (o .PJC guarda FGTS em bloco
    # proprio, ja coberto em bases_calculo) — nao e presenca comparavel.
    def _so_em(resto, usados, vv, lado):
        for kk in resto:
            if kk in usados:
                continue
            if cross and "FGTS" in kk:
                nao_comp.add("verba FGTS (o .PJC representa fora da lista de verbas)")
                continue
            out[lado].append(vv[kk]["nome"])

    _so_em(resto_a, usados_a, va, "verbas_so_a")
    _so_em(resto_b, usados_b, vb, "verbas_so_b")

    # meta / periodo (INPUT — D1)
    for campo in ["periodo_inicio", "periodo_fim", "data_ajuizamento"]:
        xa, xb = a["meta"].get(campo), b["meta"].get(campo)
        if xa != xb and (xa or xb):
            out["meta"].append({"item": campo, "a": xa, "b": xb})

    # bases/contribuicoes — numerico E config textual; aliquota tem tolerancia propria.
    # No CRUZADO (pdf x pjc), subcampo que so um formato traz nao compara — vira aviso.
    def _cmp_dicts(secao, xa_d, xb_d):
        for chave in sorted(set(xa_d) | set(xb_d)):
            da = xa_d.get(chave) if isinstance(xa_d.get(chave), dict) else {"valor": xa_d.get(chave)}
            db = xb_d.get(chave) if isinstance(xb_d.get(chave), dict) else {"valor": xb_d.get(chave)}
            for sub in sorted(set(da) | set(db)):
                sa, sb = da.get(sub), db.get(sub)
                if cross and (_vazio(sa) or _vazio(sb)):
                    if not (_vazio(sa) and _vazio(sb)):
                        nao_comp.add(f"{secao}: {chave}.{sub} (so um dos formatos traz)")
                    continue
                tol = TOL_ALIQ if "aliquota" in sub else TOL
                if _difere_any(sa, sb, tol):
                    out[secao].append({"item": f"{chave}.{sub}", "a": sa, "b": sb})

    _cmp_dicts("bases_calculo", a["bases_calculo"], b["bases_calculo"])
    _cmp_dicts("contribuicoes", a["contribuicoes"], b["contribuicoes"])

    # criterio (indices + juros + config fina de juros)
    if a["criterio_indices"] != b["criterio_indices"]:
        out["criterio"].append({"item": "indices de correcao", "a": a["criterio_indices"], "b": b["criterio_indices"]})
    if a["criterio_juros"] and b["criterio_juros"]:
        if a["criterio_juros"] != b["criterio_juros"]:
            out["criterio"].append({"item": "criterio de juros", "a": a["criterio_juros"], "b": b["criterio_juros"]})
    elif (a["criterio_juros"] or b["criterio_juros"]) and cross:
        nao_comp.add("criterio de juros (um dos formatos nao traz)")
    ja, jb = a.get("config_juros") or {}, b.get("config_juros") or {}
    if ja and jb:
        for kk in sorted(set(ja) | set(jb)):
            if _difere_any(ja.get(kk), jb.get(kk)):
                out["criterio"].append({"item": f"juros: {kk}", "a": ja.get(kk), "b": jb.get(kk)})
    elif (ja or jb) and cross:
        nao_comp.add("config fina de juros (so o .PJC traz)")

    # cartao de ponto: config da apuracao (D6) + apuracao diaria (frequencia D6 / quantidades D9)
    out["cartao"] = {"config": [], "dias": []}
    ka, kb = a.get("cartao") or {"config": {}, "dias": {}}, b.get("cartao") or {"config": {}, "dias": {}}
    tem_a = bool(ka["config"] or ka["dias"])
    tem_b = bool(kb["config"] or kb["dias"])
    if tem_a and tem_b:
        for campo in sorted(set(ka["config"]) | set(kb["config"])):
            if _difere_any(ka["config"].get(campo), kb["config"].get(campo)):
                out["cartao"]["config"].append({"item": campo,
                                                "a": ka["config"].get(campo), "b": kb["config"].get(campo)})
        for dia in sorted(set(ka["dias"]) | set(kb["dias"])):
            da, db = ka["dias"].get(dia), kb["dias"].get(dia)
            if da is None or db is None:
                out["cartao"]["dias"].append({"dia": dia, "campo": f"dia so em {'A' if da else 'B'}",
                                              "a": (da or {}).get("frequencia"), "b": (db or {}).get("frequencia")})
                continue
            for campo in sorted(set(da) | set(db)):
                xa, xb = da.get(campo), db.get(campo)
                if campo == "frequencia":
                    if (xa or "") != (xb or ""):
                        out["cartao"]["dias"].append({"dia": dia, "campo": "frequencia", "a": xa, "b": xb})
                elif _difere(xa or 0.0, xb or 0.0, 0.001):
                    out["cartao"]["dias"].append({"dia": dia, "campo": campo, "a": xa or 0.0, "b": xb or 0.0})
    elif (tem_a or tem_b) and cross:
        nao_comp.add("apuracao do cartao de ponto (so o .PJC traz)")

    # seguro-desemprego (inputs + valor da parcela)
    out["seguro_desemprego"] = []
    sa_, sb_ = a.get("seguro_desemprego") or {}, b.get("seguro_desemprego") or {}
    if sa_ and sb_:
        for kk in sorted(set(sa_) | set(sb_)):
            if _difere_any(sa_.get(kk), sb_.get(kk)):
                out["seguro_desemprego"].append({"item": kk, "a": sa_.get(kk), "b": sb_.get(kk)})
    elif (sa_ or sb_):
        if cross:
            nao_comp.add("seguro-desemprego (so o .PJC traz)")
        else:
            out["seguro_desemprego"].append({"item": "apurar",
                                             "a": "true" if sa_ else None,
                                             "b": "true" if sb_ else None})

    # totais
    ta, tb = a["totais"], b["totais"]
    if cross and (bool(ta) != bool(tb)):
        nao_comp.add("totais devido/liquido (so o PDF traz)")
    else:
        for chave in sorted(set(ta) | set(tb)):
            if _difere(ta.get(chave), tb.get(chave)):
                out["totais"].append({"item": chave, "a": ta.get(chave), "b": tb.get(chave)})

    out["nao_comparado"] = sorted(nao_comp)
    return out


# ───────────────────────── RAIZ (input) x cascata (computado) ─────────────────────────
# Um erro esta num INPUT; a cascata sao os COMPUTADOS. A raiz = o input que difere.
INPUT_MES = {"base de calculo": 14, "multiplicador": 14, "divisor": 5, "quantidade": 9, "pago": 11,
             "mes so em A": 1, "mes so em B": 1}
INPUT_VERBA_CAMPO = {"Base de calculo (total)": 14, "Valor pago": 11,
                     "incidencia FGTS": 13, "incidencia INSS": 13, "incidencia IRPF": 13,
                     "proporcionalidade": 15, "periodo da verba": 1}
INPUT_BASE_SUB = {"aliquota", "multa", "incidencia", "indice_correcao", "apurar"}
INPUT_CONTRIB_SUB = {"aliquota", "devido", "por_atividade", "tipo"}
DIM_NOME = {1: "Período de cálculo", 2: "Verbas apuradas / reflexos", 4: "Índices de correção (ADC 58)",
            5: "Divisor / maior remuneração", 6: "Frequência nos cartões de ponto",
            9: "Quantidade mensal (soma do cartão / HE)",
            10: "Dias do aviso prévio", 12: "Dias de RSR (repouso/feriado)",
            11: "Dedução de pagos (salário reclamante)",
            13: "Incidências por verba (FGTS/INSS/IRPF)",
            14: "Base de cálculo da verba (salário paradigma)",
            15: "Proporcionalidade / avos (13º, férias)",
            16: "Juros", 17: "Base FGTS", 18: "Multa 40%", 20: "IRPF", 21: "INSS empresa (Simples/desoneração)",
            22: "SAT/RAT pelo CNAE", 23: "Custas",
            25: "Seguro-desemprego"}


def _dim_qtd_reflexo(nome):
    """Quantidade/proporcao PROPRIA do reflexo -> dimensao por tipo (avos, RSR, AP)."""
    n = _norm(nome)
    if "FERIAS" in n or "13" in n or "DECIMO" in n or "TERCEIRO" in n:
        return 15   # avos de 13o/ferias -> proporcionalidade
    if "REPOUSO" in n or "RSR" in n or "DSR" in n or "FERIADO" in n:
        return 12   # dias de RSR
    if "AVISO" in n:
        return 10   # dias do aviso previo
    return 9


def _dim_base(item):
    if "multa" in item:      # fgts.multa (40%) ou multa40 -> dim 18
        return 18
    if "irpf" in item:
        return 20
    if "fgts" in item:
        return 17
    return 17


def _dim_contrib(item):
    if "empresa" in item or "segurado" in item:
        return 21
    if "sat" in item:
        return 22
    if "custas" in item:
        return 23
    return 21


def raiz(d):
    """Extrai a RAIZ (inputs que diferem) do diff, separando da cascata (computados)."""
    roots = []
    for n in d["verbas_so_a"]:
        roots.append({"dim": 2, "tipo": "verba a mais em A", "chave": n})
    for n in d["verbas_so_b"]:
        roots.append({"dim": 2, "tipo": "verba faltante em A (só em B)", "chave": n})
    for it in d["meta"]:
        roots.append({"dim": 1, "tipo": "período", "chave": it["item"], "a": it["a"], "b": it["b"]})
    for it in d["criterio"]:
        dim_c = 16 if "juros" in it["item"].lower() else 4
        roots.append({"dim": dim_c, "tipo": "critério de correção/juros", "chave": it["item"]})

    # cartao de ponto: config e frequencia sao INPUT (D6); quantidades apuradas
    # divergindo SEM config/frequencia divergir = soma/importacao errada (D9)
    cart = d.get("cartao") or {"config": [], "dias": []}
    cart_qtd_cascata = 0
    for it in cart["config"]:
        roots.append({"dim": 6, "tipo": "config da apuração do cartão",
                      "chave": f"cartao.{it['item']}", "a": it["a"], "b": it["b"]})
    dias_freq = [x for x in cart["dias"]
                 if x["campo"] == "frequencia" or x["campo"].startswith("dia so em")]
    dias_qtd = [x for x in cart["dias"] if x["campo"] != "frequencia"
                and not x["campo"].startswith("dia so em")]
    if dias_freq:
        roots.append({"dim": 6, "tipo": "frequência/batidas divergentes no cartão",
                      "chave": f"frequencia diaria ({len(dias_freq)} dia(s))"})
    if dias_qtd:
        if dias_freq or cart["config"]:
            cart_qtd_cascata = len(dias_qtd)   # consequencia da config/frequencia
        else:
            roots.append({"dim": 9, "tipo": "quantidades do cartão divergem (soma diário × importado)",
                          "chave": f"apuracao diaria ({len(dias_qtd)} registro(s))"})
    tem_cartao = bool(cart["config"] or cart["dias"])

    # seguro-desemprego: inputs = raiz D25; valor_parcela e COMPUTADO (cascata se
    # algum input divergiu; raiz se so o valor diverge — faixa/tabela errada)
    sd_itens = d.get("seguro_desemprego") or []
    sd_inputs = [it for it in sd_itens if it["item"] != "valor_parcela"]
    sd_valor = [it for it in sd_itens if it["item"] == "valor_parcela"]
    for it in sd_inputs:
        roots.append({"dim": 25, "tipo": "seguro-desemprego", "chave": f"seguro.{it['item']}",
                      "a": it["a"], "b": it["b"]})
    sd_cascata = 0
    if sd_valor:
        if sd_inputs:
            sd_cascata = 1
        else:
            roots.append({"dim": 25, "tipo": "seguro-desemprego (valor da parcela)",
                          "chave": "seguro.valor_parcela", "a": sd_valor[0]["a"], "b": sd_valor[0]["b"]})
    for it in d["bases_calculo"]:
        if it["item"].split(".")[-1] in INPUT_BASE_SUB:
            roots.append({"dim": _dim_base(it["item"]), "tipo": "config base", "chave": it["item"],
                          "a": it["a"], "b": it["b"]})
    contrib_adiadas = []
    for it in d["contribuicoes"]:
        if it["item"].split(".")[-1] in INPUT_CONTRIB_SUB:
            # segurado.aliquota e a taxa EFETIVA da tabela progressiva do INSS —
            # muda de carona quando o salario muda. So e raiz se for a UNICA suspeita.
            if it["item"] == "segurado.aliquota":
                contrib_adiadas.append(it)
                continue
            roots.append({"dim": _dim_contrib(it["item"]), "tipo": "config contribuição", "chave": it["item"],
                          "a": it["a"], "b": it["b"]})
    # PRINCIPAIS (Calculada) com mudanca de base -> a base do reflexo que incide sobre
    # elas e CASCATA (nao raiz separada). Ex.: DIFERENCA SALARIAL sobe -> 13o/ferias/
    # periculosidade/aviso SOBRE ela sobem junto.
    principais_base = set()       # principais com QUALQUER alteracao — a base do
    for v in d["verbas"]:         # reflexo deriva da principal (base, qtd, meses...)
        if v["tipo"] == "principal" and (v["campos"] or v["meses"]):
            principais_base.add(_norm(v["nome"]))

    sumidas = [_norm(x) for x in d["verbas_so_a"] + d["verbas_so_b"]]

    def _base_cascata(v):
        if v["tipo"] != "reflexo":
            return False
        n = _norm(v["nome"])
        if "SOBRE" in n:
            parent = n.split("SOBRE", 1)[1].strip()
            if principais_base and any(p in parent or parent in p or _sim_nome(parent, p) >= 0.6
                                       for p in principais_base):
                return True
            # principal removida/adicionada (D2 ja e raiz) -> reflexo orfao e cascata do D2
            if any(s in parent or parent in s or _sim_nome(parent, s) >= 0.6 for s in sumidas):
                return True
            return False  # reflexo com principal que NAO mudou -> diferenca propria = raiz
        return bool(principais_base)  # sem 'SOBRE' + principal mudou -> cascata

    cascata_reflexo = 0
    for v in d["verbas"]:
        bc = _base_cascata(v)
        # mes faltando/sobrando na verba -> totais dela mudam por consequencia:
        # a RAIZ e o mes (D1), nao a base/pago total (D14/D11)
        tem_mes_so = any(m["campo"].startswith("mes so em") for m in v["meses"])
        campos_add = set()   # campos ja reportados no nivel TOTAL (evita duplicar com o por-mes)
        for c in v["campos"]:
            if c["campo"] in INPUT_VERBA_CAMPO:
                if tem_mes_so and c["campo"] in ("Base de calculo (total)", "Valor pago"):
                    cascata_reflexo += 1
                    continue
                if c["campo"] == "Base de calculo (total)" and bc:
                    cascata_reflexo += 1
                    continue
                roots.append({"dim": INPUT_VERBA_CAMPO[c["campo"]], "tipo": "verba (total)",
                              "chave": f"{v['nome']} · {c['campo']}", "a": c["a"], "b": c["b"]})
                campos_add.add(c["campo"])
        for cm in sorted({m["campo"] for m in v["meses"] if m["campo"] in INPUT_MES}):
            if cm == "base de calculo":
                if bc:
                    cascata_reflexo += 1
                    continue
                if "Base de calculo (total)" in campos_add:   # ja reportado no total
                    continue
            if cm == "pago" and "Valor pago" in campos_add:
                continue
            dim = INPUT_MES[cm]
            if cm == "quantidade":   # avos/RSR/AP: apuracao PROPRIA do reflexo (nao coberta pela base)
                dq = _dim_qtd_reflexo(v["nome"])
                if dq != 9:
                    dim = dq
                elif tem_cartao:     # cartao divergiu -> a quantidade da verba e CONSEQUENCIA
                    cascata_reflexo += 1
                    continue
            roots.append({"dim": dim, "tipo": "verba (por mês)", "chave": f"{v['nome']} · {cm}"})

    # decide as contribuicoes ADIADAS: com raiz upstream (salario/verba/periodo),
    # a taxa efetiva do segurado e cascata; sem upstream, e raiz propria (tabela errada)
    _UPSTREAM = {1, 2, 9, 11, 14, 15}
    tem_upstream = any(r["dim"] in _UPSTREAM for r in roots)
    for it in contrib_adiadas:
        if tem_upstream:
            cascata_reflexo += 1
        else:
            roots.append({"dim": _dim_contrib(it["item"]), "tipo": "config contribuição",
                          "chave": it["item"], "a": it["a"], "b": it["b"]})

    cascata = (len(d["totais"]) + cascata_reflexo + cart_qtd_cascata + sd_cascata
               + sum(1 for v in d["verbas"] for c in v["campos"] if c["campo"] not in INPUT_VERBA_CAMPO)
               + sum(1 for v in d["verbas"] for m in v["meses"] if m["campo"] not in INPUT_MES)
               + sum(1 for it in d["bases_calculo"] if it["item"].split(".")[-1] not in INPUT_BASE_SUB)
               + sum(1 for it in d["contribuicoes"] if it["item"].split(".")[-1] not in INPUT_CONTRIB_SUB))

    seen, uniq = set(), []
    for r in roots:
        key = (r["dim"], r["chave"])
        if key in seen:
            continue
        seen.add(key)
        r["dim_nome"] = DIM_NOME.get(r["dim"], "?")
        uniq.append(r)
    dims = sorted({r["dim"] for r in uniq})
    return {"raiz": uniq, "dimensoes_raiz": dims, "cascata_qtd": cascata}


# ─────────────────── OTICA (reclamante x reclamada) ───────────────────
# Efeito do item no VALOR DEVIDO do calculo A: +1 = A apura MAIS; -1 = A apura MENOS.
# 'Valor pago' e INVERTIDO (pago maior -> deduz mais -> devido menor).
_EFEITO_INVERTIDO = {"Valor pago", "pago"}


def _efeito_raiz(x):
    """Retorna delta EFETIVO no devido de A (float>0 = A apura a mais), ou None (config)."""
    if x["tipo"].startswith("verba a mais"):
        return 1.0
    if x["tipo"].startswith("verba faltante"):
        return -1.0
    a, b = _f(x.get("a")), _f(x.get("b"))
    if a is None or b is None:
        return None   # config/criterio/datas — sem sinal, e desconformidade a conferir
    delta = a - b
    campo = x["chave"].split("·")[-1].strip()
    if campo in _EFEITO_INVERTIDO:
        delta = -delta
    return delta


def com_otica(r, otica):
    """Anota cada item da raiz com a favorabilidade sob a otica do cliente.

    Convencao de uso: A = calculo ANALISADO (da outra parte / do aluno);
    B = a REFERENCIA (nosso calculo / gabarito).
    otica='reclamada' (cliente paga): A apurando A MAIS = IMPUGNAR.
    otica='reclamante' (cliente recebe): A apurando A MENOS = IMPUGNAR."""
    if otica not in ("reclamada", "reclamante"):
        return r
    for x in r["raiz"]:
        ef = _efeito_raiz(x)
        if ef is None or abs(ef) < TOL:
            x["favorabilidade"] = "CONFERIR"     # desconformidade de config/criterio
            continue
        a_mais = ef > 0
        impugna = a_mais if otica == "reclamada" else not a_mais
        x["favorabilidade"] = "IMPUGNAR" if impugna else "FAVORAVEL"
    r["otica"] = otica
    r["impugnar"] = [x for x in r["raiz"] if x.get("favorabilidade") == "IMPUGNAR"]
    return r


# ───────────────────────── relatorio ─────────────────────────
def relatorio(d, nome_a="CALC A", nome_b="CALC B", minucioso=False, otica=None):
    L = []
    def add(s=""): L.append(s)
    add("=" * 78)
    add(f"DIFERENCAS  —  A = {nome_a}   |   B = {nome_b}")
    if otica:
        add(f"OTICA: cliente e {otica.upper()}  (A = calculo analisado; B = referencia)")
    add("=" * 78)

    # RAIZ do erro (o input alterado) — a causa, separada da cascata (computados)
    r = com_otica(raiz(d), otica)
    if r["raiz"]:
        add("")
        add("★ RAIZ DO ERRO (o que foi alterado — a causa):")
        for x in r["raiz"]:
            det = ""
            if x.get("a") is not None or x.get("b") is not None:
                det = f"   [{_fmt(x.get('a'))} -> {_fmt(x.get('b'))}]"
            tag = f"  << {x['favorabilidade']}" if x.get("favorabilidade") else ""
            add(f"    ▸ D{x['dim']} · {x['dim_nome']}  ·  {x['chave']}{det}{tag}")
        add(f"    ({r['cascata_qtd']} diferencas em CASCATA — consequencia, detalhadas abaixo)")
        if otica:
            n_imp = len(r.get("impugnar", []))
            add(f"    OTICA {otica.upper()}: {n_imp} ponto(s) a IMPUGNAR; "
                f"FAVORAVEL nao se impugna; CONFERIR = desconformidade de criterio/config.")

    cart = d.get("cartao") or {"config": [], "dias": []}
    total_difs = (len(d["verbas_so_a"]) + len(d["verbas_so_b"]) + sum(len(v["campos"]) + len(v["meses"]) for v in d["verbas"])
                  + len(d["bases_calculo"]) + len(d["contribuicoes"]) + len(d["criterio"]) + len(d["totais"]) + len(d["meta"])
                  + len(cart["config"]) + len(cart["dias"]) + len(d.get("seguro_desemprego") or []))
    if total_difs == 0:
        add("\nNENHUMA diferenca encontrada (dentro da tolerancia de R$ 0,01).")
        return "\n".join(L)

    if d["verbas_so_a"]:
        add(f"\n▸ VERBAS so em A ({len(d['verbas_so_a'])}):")
        for n in d["verbas_so_a"]:
            add(f"    - {n}")
    if d["verbas_so_b"]:
        add(f"\n▸ VERBAS so em B ({len(d['verbas_so_b'])}):")
        for n in d["verbas_so_b"]:
            add(f"    - {n}")

    if d["verbas"]:
        add(f"\n▸ VERBAS com diferenca ({len(d['verbas'])}):")
        raiz_chaves = {x["chave"].split(" · ")[0] for x in r["raiz"] if " · " in x.get("chave", "")}
        for v in d["verbas"]:
            marca = "RAIZ" if v["nome"] in raiz_chaves else "cascata"
            if minucioso:
                add(f"\n  ● {v['nome']}  [{v['tipo']} · {marca}]")
                for c in v["campos"]:
                    delta = f"  (Δ {_fmt(c['delta'])})" if c.get("delta") is not None else ""
                    add(f"      {c['campo']:32} A={_fmt(c['a']):>15}  B={_fmt(c['b']):>15}{delta}")
                if v["meses"]:
                    add(f"      — por mes ({len(v['meses'])} diferenca(s)):")
                    for m in v["meses"][:40]:
                        add(f"          {str(m['periodo'])[:18]:18} {m['campo']:16} A={_fmt(m['a']):>13}  B={_fmt(m['b']):>13}")
                    if len(v["meses"]) > 40:
                        add(f"          ... (+{len(v['meses'])-40} diferencas de mes)")
            else:
                # 1 linha por verba: o que o calculista precisa; detalhe = --minucioso
                hist = next((c for c in v["campos"] if c["campo"] == "Valor historico apurado"), None)
                resumo = (f"historico {_fmt(hist['a'])} -> {_fmt(hist['b'])} (Δ {_fmt(hist.get('delta'))})"
                          if hist else f"{len(v['campos'])} campo(s)")
                n_meses = len({m["periodo"] for m in v["meses"]})
                n_pts = len(v["meses"])
                add(f"  ● {v['nome'][:52]:52} [{marca:7}] {resumo}"
                    f"{f'  · {n_meses} meses ({n_pts} pontos)' if n_pts else ''}")

    def bloco(titulo, itens):
        if itens:
            add(f"\n▸ {titulo} ({len(itens)}):")
            for it in itens:
                add(f"      {it['item']:34} A={_fmt(it['a']):>15}  B={_fmt(it['b']):>15}")

    bloco("BASES DE CALCULO", d["bases_calculo"])
    bloco("CONTRIBUICOES", d["contribuicoes"])
    bloco("TOTAIS", d["totais"])
    bloco("SEGURO-DESEMPREGO", d.get("seguro_desemprego") or [])
    if cart["config"] or cart["dias"]:
        add(f"\n▸ CARTAO DE PONTO ({len(cart['config'])} config, {len(cart['dias'])} registro(s) diario(s)):")
        for it in cart["config"]:
            add(f"      config.{it['item']:30} A={_fmt(it['a']):>15}  B={_fmt(it['b']):>15}")
        for m in cart["dias"][:40]:
            add(f"      {m['dia']:12} {m['campo']:26} A={_fmt(m['a']):>13}  B={_fmt(m['b']):>13}")
        if len(cart["dias"]) > 40:
            add(f"      ... (+{len(cart['dias'])-40} registros diarios)")
    if d["criterio"]:
        add(f"\n▸ CRITERIO (indices/juros):")
        for it in d["criterio"]:
            add(f"      {it['item']}:")
            add(f"          A: {it['a']}")
            add(f"          B: {it['b']}")

    if d.get("nao_comparado"):
        add("\n▸ NAO COMPARADO (formatos diferentes — PDF x .PJC; nao e igualdade, e cegueira):")
        for x in d["nao_comparado"]:
            add(f"      - {x}")

    add("\n" + "-" * 78)
    add(f"TOTAL de pontos de diferenca: {total_difs}")
    return "\n".join(L)


def analise(calc, nome="CALC"):
    """Imprime a analise minuciosa de UM calculo (verba a verba)."""
    L = [f"=== ANALISE: {nome} ===", f"meta: {json.dumps(calc['meta'], ensure_ascii=False)}"]
    L.append(f"\nVERBAS ({len(calc['verbas'])}):")
    for k, v in calc["verbas"].items():
        L.append(f"  ● {v['nome']} [{v['tipo']}]  hist={_fmt(v['valor_historico'])} "
                 f"corr={_fmt(v['valor_corrigido'])} juros={_fmt(v['valor_juros'])} "
                 f"pago={_fmt(v['valor_pago'])} base={_fmt(v['base_total'])} meses={len(v['meses'])}")
    return "\n".join(L)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    otica = None
    for f in flags:
        if f.startswith("--otica="):
            otica = f.split("=", 1)[1].strip().lower()
        elif f == "--otica" or f.startswith("--otica-"):
            otica = f.replace("--otica-", "").replace("--otica", "").strip("-") or None
    if otica not in (None, "reclamada", "reclamante"):
        print(f"otica invalida: {otica} (use --otica=reclamada ou --otica=reclamante)")
        return
    if not args:
        print(__doc__)
        return
    a = carregar(args[0])
    if len(args) == 1:
        print(analise(a, Path(args[0]).name))
        return
    b = carregar(args[1])
    d = diff(a, b)
    if "--json" in flags:
        d["raiz_analise"] = com_otica(raiz(d), otica)
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(relatorio(d, Path(args[0]).name, Path(args[1]).name,
                        minucioso="--minucioso" in flags, otica=otica))


if __name__ == "__main__":
    main()
