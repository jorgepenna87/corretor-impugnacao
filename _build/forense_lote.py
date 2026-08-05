# -*- coding: utf-8 -*-
"""
forense_lote.py — roda TODOS os alunos de EXERCÍCIOS PRONTOS (marco16) no motor
comparar_calculos e produz o relatorio do que o app atual esta deixando passar.

Por aluno:
- acha a PLANILHA (relatorio PJe-Calc do proprio aluno, PDF) e o .PJC
- motor: diff(aluno, gabarito) PDF x PDF (resultado) e PJC x PJC (parametros/config)
- saude do parse: bruto < liquido, totais ausentes, PDF ilegivel

Saida: _build/_FORENSE_MARCO16.md + resumo no console.
"""
from __future__ import annotations
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, r"C:\Users\jorge\Documents\CLAUDE\comparar-calculos")
import comparar_calculos as C  # noqa: E402

DRIVE_BASE = Path(r"G:\Meu Drive\CURSOS EM VIDEO\IMPUGNAÇÃO - EXERCÍCIOS")
# (id, subpasta dos alunos no Drive, pasta_unica=True quando a pasta JA E um aluno so)
EXERCICIOS = [
    ("marco16", r"MARÇO 16 - EXERCÍCIO\EXERCÍCIOS PRONTOS", False),
    ("abril13", r"ABRIL 13 - EXERCICIO\RESULTADOS DOS ALUNOS", False),
    ("junho22", r"JUNHO 22 - EXERCÍCIO\PASTA DE RESULTADOS DOS ALUNOS", False),
    ("setembro15", r"SETEMBRO 15 - EXERCÍCIO\EXERCICIO MIGUEL LEMOS", True),
]


def _norm(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def acha_arquivos(pasta: Path):
    """Planilha do ALUNO (nao o orcamento do autor, nao parecer/impugnacao) + .PJC."""
    pdfs = list(pasta.glob("*.pdf")) + list(pasta.glob("*.PDF"))
    pjcs = list(pasta.glob("*.pjc")) + list(pasta.glob("*.PJC"))
    ruim = ("orcamento", "parecer", "impugna", "sentenc", "peticao")
    def score(p):
        n = _norm(p.name)
        if any(r in n for r in ruim):
            return -1
        s = 0
        if "planilha" in n: s += 10
        if "calculo" in n or "clculo" in n: s += 5
        if "relatorio" in n: s += 5
        return s
    cand = sorted(((score(p), p) for p in pdfs), key=lambda t: -t[0])
    pdf = cand[0][1] if cand and cand[0][0] >= 0 else None
    if cand and cand[0][0] < 5:   # nada com nome bom — marca ambiguidade
        pdf_amb = True
    else:
        pdf_amb = False
    return pdf, (pjcs[0] if pjcs else None), pdf_amb


def resumo_raiz(r, max_itens=10):
    linhas = []
    for x in r["raiz"][:max_itens]:
        val = ""
        if x.get("a") is not None or x.get("b") is not None:
            val = f" [{x.get('a')} vs gab {x.get('b')}]"
        linhas.append(f"D{x['dim']} {x['dim_nome']}: {x['chave']}{val}")
    if len(r["raiz"]) > max_itens:
        linhas.append(f"... +{len(r['raiz']) - max_itens} itens de raiz")
    return linhas


def roda_exercicio(ex_id, sub_drive, pasta_unica):
    drive = DRIVE_BASE / sub_drive
    gab_pdf = C.carregar(str(HERE / ex_id / "GABARITO_relatorio.pdf"))
    gab_pjc = C.carregar(str(HERE / ex_id / "GABARITO.PJC"))
    out_md = HERE / f"_FORENSE_{ex_id.upper()}.md"
    L = [f"# FORENSE {ex_id.upper()} — lote completo (motor comparar_calculos)", ""]
    stats = {"ok": 0, "sem_pdf": 0, "sem_pjc": 0, "crash_pdf": 0, "parse_suspeito": 0}
    tab = []

    pastas = [drive] if pasta_unica else sorted(drive.iterdir())
    for pasta in pastas:
        if not pasta.is_dir():
            continue
        aluno = pasta.name
        pdf, pjc, amb = acha_arquivos(pasta)
        L.append(f"\n## {aluno}")
        linha = {"aluno": aluno, "pdf": bool(pdf), "pjc": bool(pjc),
                 "dims_pdf": None, "dims_pjc": None, "flags": []}
        if amb and pdf:
            linha["flags"].append(f"pdf-ambiguo:{pdf.name}")

        # ── resultado (PDF x PDF) ──
        if pdf is None:
            L.append("- SEM planilha PDF identificavel")
            stats["sem_pdf"] += 1
        else:
            L.append(f"- planilha: `{pdf.name}`")
            try:
                al = C.carregar(str(pdf))
                d = C.diff(al, gab_pdf)
                r = C.raiz(d)
                linha["dims_pdf"] = r["dimensoes_raiz"]
                t = al.get("totais") or {}
                td, lq = t.get("total_devido_reclamado"), t.get("liquido_devido_reclamante")
                L.append(f"- totais do aluno: total_devido={td}  liquido={lq}  "
                         f"(gab: {gab_pdf['totais']['total_devido_reclamado']} / "
                         f"{gab_pdf['totais']['liquido_devido_reclamante']})")
                if td is None or lq is None:
                    linha["flags"].append("totais-nao-parseados")
                    stats["parse_suspeito"] += 1
                elif td < lq:
                    linha["flags"].append("BRUTO<LIQUIDO (parse suspeito)")
                    stats["parse_suspeito"] += 1
                L.append(f"- **raiz PDF** dims={r['dimensoes_raiz']} ({len(r['raiz'])} itens, cascata {r['cascata_qtd']}):")
                for ln in resumo_raiz(r):
                    L.append(f"    - {ln}")
                stats["ok"] += 1
            except Exception as e:
                L.append(f"- CRASH no parse do PDF: `{type(e).__name__}: {e}`")
                linha["flags"].append(f"crash-pdf:{type(e).__name__}")
                stats["crash_pdf"] += 1

        # ── parametros/config (PJC x PJC) ──
        if pjc is None:
            L.append("- SEM .PJC")
            stats["sem_pjc"] += 1
        else:
            try:
                alp = C.carregar(str(pjc))
                dp = C.diff(alp, gab_pjc)
                rp = C.raiz(dp)
                linha["dims_pjc"] = rp["dimensoes_raiz"]
                L.append(f"- **raiz PJC** dims={rp['dimensoes_raiz']} ({len(rp['raiz'])} itens, cascata {rp['cascata_qtd']}):")
                for ln in resumo_raiz(rp, 8):
                    L.append(f"    - {ln}")
            except Exception as e:
                L.append(f"- CRASH no parse do PJC: `{type(e).__name__}: {e}`")
                linha["flags"].append(f"crash-pjc:{type(e).__name__}")
        tab.append(linha)

    # ── resumo executivo ──
    L.insert(2, "## Resumo executivo\n")
    freq = {}
    for ln in tab:
        for dm in (ln["dims_pdf"] or []) + (ln["dims_pjc"] or []):
            freq[dm] = freq.get(dm, 0) + 1
    L.insert(3, f"- alunos: {len(tab)} | com PDF ok: {stats['ok']} | sem PDF: {stats['sem_pdf']} | "
                f"crash PDF: {stats['crash_pdf']} | sem PJC: {stats['sem_pjc']} | parse suspeito: {stats['parse_suspeito']}")
    L.insert(4, f"- dims mais frequentes (raiz): " +
                ", ".join(f"D{k}×{v}" for k, v in sorted(freq.items(), key=lambda t: -t[1])))
    L.insert(5, "")

    out_md.write_text("\n".join(L), encoding="utf-8")
    print(f"\n===== {ex_id.upper()} — relatorio: {out_md.name} =====")
    print(f"alunos={len(tab)} pdf_ok={stats['ok']} sem_pdf={stats['sem_pdf']} "
          f"crash_pdf={stats['crash_pdf']} sem_pjc={stats['sem_pjc']} parse_suspeito={stats['parse_suspeito']}")
    print("dims raiz mais frequentes:", ", ".join(f"D{k}x{v}" for k, v in sorted(freq.items(), key=lambda t: -t[1])))
    for ln in tab:
        print(f"  {ln['aluno'][:34]:34} pdf={ln['dims_pdf']} pjc={ln['dims_pjc']} "
              f"{'FLAGS: ' + '; '.join(ln['flags']) if ln['flags'] else ''}")


def main():
    so = [a for a in sys.argv[1:] if not a.startswith("-")]
    for ex_id, sub, unica in EXERCICIOS:
        if so and ex_id not in so:
            continue
        try:
            roda_exercicio(ex_id, sub, unica)
        except Exception as e:
            print(f"===== {ex_id}: FALHOU ({type(e).__name__}: {e}) =====")


if __name__ == "__main__":
    main()
