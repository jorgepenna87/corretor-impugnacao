# -*- coding: utf-8 -*-
"""
exrunner.py — runner generico para qualquer exercicio (espelha engine.py).
Uso:
  python _build/exrunner.py probe      <id>   # imprime params + verbas do GABARITO
  python _build/exrunner.py selfcheck  <id>   # engine reproduz exercicios/<id>/gabarito.json?
  python _build/exrunner.py grade      <id>   # nota de cada aluno em _build/<id>/amostras
  python _build/exrunner.py all        <id>   # selfcheck + grade

Estrutura esperada:
  _build/<id>/GABARITO.PJC
  _build/<id>/GABARITO_relatorio.pdf
  _build/<id>/config.json
  _build/<id>/amostras/*.PJC
  exercicios/<id>/gabarito.json   (gerado por build_gabarito.py)
"""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine

BUILD = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(BUILD)


def _gpjc(exid):
    return os.path.join(BUILD, exid, 'GABARITO.PJC')


def _gab(exid):
    return json.load(open(os.path.join(PROJ, 'exercicios', exid, 'gabarito.json'), encoding='utf-8'))


def probe(exid):
    g = engine.extract(_gpjc(exid))
    print(f"=== PROBE {exid} ===")
    for k, v in g.items():
        if k == '_verbas':
            continue
        print(f"  {k:32} = {v!r}")
    print(f"  verbas ({len(g['_verbas'])}):")
    for key, vd in g['_verbas'].items():
        print(f"    [{vd['tipo']}] {vd['descricao']}")


def selfcheck(exid):
    gab = _gab(exid)
    gabflat = engine.extract(_gpjc(exid))
    bad = []
    for ck in gab['checkpoints']:
        got = gabflat.get(ck['key'])
        st = engine.cmp_val(ck.get('tipo', 'texto'), got, ck['esperado'], ck.get('tolerancia', 0))
        if st != 'OK':
            bad.append((ck['key'], got, ck['esperado']))
    n = len(gab['checkpoints'])

    # selfcheck verbas_anchor: gabarito contra si mesmo deve ser 100% OK
    anchors = gab.get('verbas_anchor', [])
    if anchors and gab.get('verba_check', True) is not False:
        r = engine.grade(gabflat, gab)
        for b in r['boletim']:
            if b.get('dimensao') == 2 and b['status'] != 'OK':
                bad.append((b['key'], b.get('seu_valor'), '(ancora)'))
        n += len(anchors)

    if not bad:
        print(f"=== SELFCHECK {exid}: OK — {n}/{n} itens reproduzem (incl. {len(anchors)} anchors) ===")
    else:
        print(f"=== SELFCHECK {exid}: {len(bad)}/{n} FALHAM ===")
        for k, got, exp in bad:
            print(f"   FAIL {k}: engine={got!r} esperado={exp!r}")
    return bad


def grade(exid):
    gab = _gab(exid)
    gab['_verbas_gab'] = engine.extract(_gpjc(exid))['_verbas']
    pjcs = sorted(glob.glob(os.path.join(BUILD, exid, 'amostras', '*.PJC')))
    print(f"=== GRADE {exid}: {len(pjcs)} alunos ===")
    for p in pjcs:
        try:
            sf = engine.extract(p)
            r = engine.grade(sf, gab)
            div = [b['key'] for b in r['boletim'] if b['status'] != 'OK']
            print(f"  {os.path.basename(p):30} nota={r['nota_calculo']:4.1f}  "
                  f"{int(r['peso_ok'])}/{int(r['peso_tot'])}  div: {', '.join(div) or '-'}")
        except Exception as e:
            print(f"  {os.path.basename(p):30} ERRO: {e}")


if __name__ == '__main__':
    cmd, exid = sys.argv[1], sys.argv[2]
    if cmd == 'all':
        selfcheck(exid); grade(exid)
    else:
        {'probe': probe, 'selfcheck': selfcheck, 'grade': grade}[cmd](exid)
