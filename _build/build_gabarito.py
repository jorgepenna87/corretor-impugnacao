#!/usr/bin/env python3
"""
build_gabarito.py — Gera gabarito.json a partir do .PJC + PDF de relatório + config.

Uso:
  python build_gabarito.py --pjc _build/gabarito/GABARITO.PJC \
      --relatorio _build/gabarito/GABARITO_relatorio.pdf \
      --config _build/gabarito/config_marco16.json \
      --out exercicios/marco16/gabarito.json
"""

import argparse
import json
import zipfile
import re
import unicodedata
from datetime import timezone, datetime
from pathlib import Path
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def epoch_to_iso(ms_str):
    """Epoch millis (string) → 'YYYY-MM-DD' em UTC."""
    if not ms_str or ms_str == "null":
        return None
    ts = int(ms_str) / 1000
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def safe_float(v, default=None):
    if v is None or v == "null":
        return default
    try:
        return round(float(v), 2)
    except (ValueError, TypeError):
        return default


def normalize_text(s):
    """Uppercase + sem acentos + trim — chave de comparação de verbas."""
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_str.upper().strip()


# ---------------------------------------------------------------------------
# Parse PJC
# ---------------------------------------------------------------------------

def load_pjc(path):
    """Descompacta o .PJC e parseia o XML. Retorna ElementTree root."""
    with zipfile.ZipFile(path) as z:
        inner_name = z.namelist()[0]
        data = z.read(inner_name)
    # XML usa ISO-8859-1 com entidades numéricas HTML (&#xxx;).
    # ElementTree parseia direto dos bytes e resolve tudo.
    return ET.fromstring(data)


def verbas_principais(root):
    """
    Retorna lista de {descricao, base, devido} das verbas <Calculada> (NAO Reflexo).
    Soma APENAS ocorrencias diretas em verba/ocorrencias/OcorrenciaDeVerba.
    NAO usa .iter() na verba inteira (duplicaria o valor via <calculo><Calculo> aninhado).
    """
    out = []
    vroot = root.find('.//verbas')
    if vroot is None:
        return out
    for el in vroot.iter():
        if el.tag == 'Calculada' and el.find('descricao') is not None:
            occ = el.find('ocorrencias')
            b = dv = 0.0
            if occ is not None:
                for o in occ.iter('OcorrenciaDeVerba'):
                    vb = o.findtext('base')
                    vd = o.findtext('devido')
                    if vb and vb != 'null':
                        b += float(vb)
                    if vd and vd != 'null':
                        dv += float(vd)
            out.append({
                'descricao': el.findtext('descricao').strip(),
                'base': round(b, 2),
                'devido': round(dv, 2),
            })
    return out


def extract_verbas(root):
    """
    Retorna lista de dicts:
      { nome, descricao, nome_norm, descricao_norm, total_devido }
    Usa 'nome' como chave única (descricao é compartilhada entre reflexos).
    """
    verbas = []
    verba_set = root.find("verbas/Set")
    if verba_set is None:
        return verbas
    for verba_elem in verba_set:
        nome = verba_elem.findtext("nome") or ""
        desc = verba_elem.findtext("descricao") or ""
        total = 0.0
        ocorrencias = verba_elem.find("ocorrencias")
        if ocorrencias is not None:
            for s in ocorrencias:
                for occ in s:
                    d = occ.findtext("devido")
                    if d and d != "null":
                        total += float(d)
        verbas.append({
            "nome": nome,
            "descricao": desc,
            "nome_norm": normalize_text(nome),
            "descricao_norm": normalize_text(desc),
            "total_devido": round(total, 2),
        })
    return verbas


def extract_params(root):
    """
    Extrai todos os keypaths relevantes do XML.
    Retorna dict plano com valores já convertidos (datas → ISO, floats → float).
    """
    p = {}

    # --- Período ---
    for tag in ["dataAdmissao", "dataDemissao", "dataAjuizamento",
                "dataInicioCalculo", "dataTerminoCalculo"]:
        p[tag] = epoch_to_iso(root.findtext(tag))

    # --- Remuneração / jornada ---
    p["valorMaiorRemuneracao"] = safe_float(root.findtext("valorMaiorRemuneracao"))
    p["valorUltimaRemuneracao"] = safe_float(root.findtext("valorUltimaRemuneracao"))
    p["valorCargaHorariaPadrao"] = safe_float(root.findtext("valorCargaHorariaPadrao"))
    p["sabadoDiaUtil"] = root.findtext("sabadoDiaUtil")
    p["diaFechamentoMes"] = root.findtext("diaFechamentoMes")
    p["regimeDoContrato"] = root.findtext("regimeDoContrato")
    p["tipoCalculo"] = root.findtext("tipoCalculo")

    # --- Prescrição ---
    p["prescricaoFgts"] = root.findtext("prescricaoFgts")
    p["prescricaoQuinquenal"] = root.findtext("prescricaoQuinquenal")

    # --- Parâmetros de atualização (índices/correção) ---
    pa = root.find("parametrosDeAtualizacao")
    if pa is not None and len(pa):
        pa = list(pa)[0]  # primeiro ParametroDeAtualizacao
        p["indiceTrabalhista"] = pa.findtext("indiceTrabalhista")
        p["combinarOutroIndice"] = pa.findtext("combinarOutroIndice")
        p["outroIndiceTrabalhista"] = pa.findtext("outroIndiceTrabalhista")
        p["apartirDeOutroIndice"] = epoch_to_iso(pa.findtext("apartirDeOutroIndice"))
        p["indiceDeCorrecaoDoFGTS"] = pa.findtext("indiceDeCorrecaoDoFGTS")
        p["indiceDeCorrecaoDasCustas"] = pa.findtext("indiceDeCorrecaoDasCustas")
        p["juros"] = pa.findtext("juros")
        p["combinarOutroJuros"] = pa.findtext("combinarOutroJuros")

    # --- Juros: taxa final ---
    apuracoes = root.findall(".//ApuracaoDeJuros")
    if apuracoes:
        last = apuracoes[-1]
        p["taxaDeJuros"] = safe_float(last.findtext("taxaDeJuros"))

    # --- FGTS ---
    fgts = root.find(".//fgts/Fgts")
    if fgts is not None:
        p["fgtsAliquota"] = fgts.findtext("aliquota")
        p["incidenciaDoFgts"] = fgts.findtext("incidenciaDoFgts")
        p["multaDoFgts"] = fgts.findtext("multaDoFgts")
        p["excluirAvisoDaMulta"] = fgts.findtext("excluirAvisoDaMulta")
        p["fgtsComporPrincipal"] = fgts.findtext("comporPrincipal")

    # --- INSS ---
    inss = root.find(".//inss/Inss")
    if inss is not None:
        p["tipoAliquotaEmpregador"] = inss.findtext("tipoAliquotaEmpregador")
        p["aliquotaEmpresaFixa"] = safe_float(inss.findtext("aliquotaEmpresaFixa"))
        p["aliquotaRATFixa"] = safe_float(inss.findtext("aliquotaRATFixa"))
        p["apurarRATPorAtividade"] = inss.findtext("apurarRATPorAtividade")
        p["tipoAliquotaSegurado"] = inss.findtext("tipoAliquotaSegurado")

    # --- IRPF ---
    irpf = root.find(".//irpf")
    if irpf is not None:
        # Buscar na subárvore (pode ter sub-elemento IRPF)
        p["apurarImpostoRenda"] = (
            irpf.findtext("apurarImpostoRenda")
            or root.findtext(".//apurarImpostoRenda")
        )
        p["incidirSobreJurosDeMora"] = (
            irpf.findtext("incidirSobreJurosDeMora")
            or root.findtext(".//incidirSobreJurosDeMora")
        )

    # --- Custas ---
    custas = root.find(".//custasJudiciais/CustasJudiciais")
    if custas is not None:
        p["tipoDeCustasDeConhecimentoDoReclamado"] = custas.findtext(
            "tipoDeCustasDeConhecimentoDoReclamado"
        )
        p["valorConhecimentoDoReclamado"] = safe_float(
            custas.findtext("valorConhecimentoDoReclamado")
        )
        p["pisoCustasConhecimentoReclamado"] = safe_float(
            custas.findtext("pisoCustasConhecimentoReclamado")
        )

    return p


# ---------------------------------------------------------------------------
# Ler total do relatório PDF
# ---------------------------------------------------------------------------

def extract_pdf_totals(pdf_path):
    """
    Tenta extrair os totais do relatório PDF com pdfplumber.
    Retorna dict com os totais ou None se não conseguir.
    """
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        print("  [aviso] pdfplumber não instalado — pulando extração de PDF")
        return {}

    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"

    patterns = {
        "totalDevidoReclamado": r"Total Devido pelo Reclamado[^\d]*([\d.]+,\d{2})",
        "liquidoReclamante": r"L[ií]quido Devido ao Reclamante[^\d]*([\d.]+,\d{2})",
        "brutoReclamante": r"Bruto Devido ao Reclamante[^\d]*([\d.]+,\d{2})",
        "depositoFGTS": r"Dep[oó]sito FGTS[^\d]*([\d.]+,\d{2})",
        "multaFGTS": r"Multa\s*40%[^\d]*([\d.]+,\d{2})",
        "inssEmpresa": r"INSS Empresa[^\d]*([\d.]+,\d{2})",
        "sat": r"SAT[^\d]*([\d.]+,\d{2})",
        "honorarios": r"Honor[aá]rios[^\d]*([\d.]+,\d{2})",
        "custas": r"Custas[^\d]*([\d.]+,\d{2})",
    }

    totais = {}
    for key, pat in patterns.items():
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val_str = m.group(1).replace(".", "").replace(",", ".")
            totais[key] = round(float(val_str), 2)

    return totais


# ---------------------------------------------------------------------------
# Montar gabarito.json
# ---------------------------------------------------------------------------

def build_gabarito(pjc_path, relatorio_path, config_path, out_path):
    print(f"[1] Parseando {pjc_path}...")
    root = load_pjc(pjc_path)
    params = extract_params(root)
    verbas = extract_verbas(root)

    print(f"[2] Lendo config {config_path}...")
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    print(f"[3] Lendo totais do PDF {relatorio_path}...")
    pdf_totais = extract_pdf_totals(relatorio_path)
    # Se o PDF não foi extraído, usar os totais hardcoded do config (se presentes)
    totais_config = config.get("totais_hardcoded", {})
    totais = {**pdf_totais, **totais_config}  # hardcoded verificado tem prioridade; PDF preenche lacunas

    print("[4] Montando checkpoints...")
    checkpoints = []
    for cp_def in config.get("checkpoints_def", []):
        key = cp_def["key"]
        val = params.get(key)
        if val is None:
            # Tenta caminho alternativo definido no config
            alt = cp_def.get("alt_key")
            if alt:
                val = params.get(alt)
        cp = {
            "key": key,
            "dimensao": cp_def["dimensao"],
            "label": cp_def["label"],
            "tipo": cp_def["tipo"],
            "esperado": val,
            "tolerancia": cp_def.get("tolerancia", 0),
            "peso": cp_def.get("peso", 1),
        }
        if "dica" in cp_def:
            cp["dica"] = cp_def["dica"]
        checkpoints.append(cp)

    print("[4b] Montando verbas_anchor (base de cálculo de verbas principais)...")
    peso_verba = config.get("peso_verba", 5)
    verbas_anchor = []
    if config.get("verba_check", True):
        for vp in verbas_principais(root):
            verbas_anchor.append({
                "label": vp["descricao"],
                "base": vp["base"],
                "devido": vp["devido"],
                "peso": peso_verba,
            })

    print("[5] Montando lista de verbas...")
    # Verbas por nome_norm (chave exata) — para matching estrito
    verbas_by_nome = []
    for v in verbas:
        if not v["nome"]:
            continue  # skip empty
        verbas_by_nome.append({
            "nome": v["nome"],
            "nome_norm": v["nome_norm"],
            "descricao": v["descricao"],
            "descricao_norm": v["descricao_norm"],
            "devido": v["total_devido"],
            "tolerancia": config.get("tolerancia_verba_percentual", 0.5),
            "match_by": "nome_norm",
        })

    # Verbas por descricao_norm (chave compartilhada) — para matching por categoria
    # Agrega verbas de mesma descricao (o que é razoável para cruzar com alunos)
    from collections import defaultdict
    desc_agg = defaultdict(lambda: {"devido": 0.0, "descricao": "", "nomes": []})
    for v in verbas:
        if not v["descricao"]:
            continue
        k = v["descricao_norm"]
        desc_agg[k]["devido"] += v["total_devido"]
        desc_agg[k]["descricao"] = v["descricao"]
        desc_agg[k]["nomes"].append(v["nome"])
    verbas_by_desc = []
    for k, info in desc_agg.items():
        verbas_by_desc.append({
            "descricao": info["descricao"],
            "descricao_norm": k,
            "devido": round(info["devido"], 2),
            "tolerancia": config.get("tolerancia_verba_percentual", 0.5),
            "match_by": "descricao_norm",
        })

    verbas_out = verbas_by_nome  # principal (para matching exato)
    verbas_por_descricao = verbas_by_desc  # alternativa (para matching por categoria)

    gabarito = {
        "exercicio": config["exercicio"],
        "checkpoints": checkpoints,
        "verbas_anchor": verbas_anchor,
        "verbas": verbas_out,
        "verbas_por_descricao": verbas_por_descricao,
        "totais": totais,
        "textChecklist": config.get("textChecklist", []),
    }

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(gabarito, f, ensure_ascii=False, indent=2)

    print(f"\nOK Gerado: {out_path}")
    print(f"  Checkpoints: {len(checkpoints)}")
    print(f"  Verbas anchor: {len(verbas_anchor)}")
    print(f"  Verbas (por nome): {len(verbas_out)}")
    print(f"  Verbas (por descricao): {len(verbas_por_descricao)}")
    print(f"  Totais: {list(totais.keys())}")
    print("\nVerbas anchor do gabarito:")
    for va in verbas_anchor:
        print(f"  [{va['label']}] base={va['base']} devido={va['devido']} peso={va['peso']}")
    print("\nVerbas do gabarito (por descricao):")
    for v in verbas_por_descricao:
        print(f"  [{v['descricao']}] devido={v['devido']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera gabarito.json para o app corretor.")
    parser.add_argument("--pjc", required=True)
    parser.add_argument("--relatorio", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    build_gabarito(args.pjc, args.relatorio, args.config, args.out)
