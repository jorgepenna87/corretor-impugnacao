# -*- coding: utf-8 -*-
"""
engine.py — fonte unica da verdade do corretor de impugnacao (SEM IA).
Parse exato do .PJC (ZIP+XML) -> dict plano de parametros + config de verbas.
Compara aluno x gabarito. O app JS espelha esta logica.

NADA de recalcular valor monetario de verba a partir do XML (PJe-Calc computa;
reproduzir gera erro). Tudo que e' graduado e' valor EXATO single-value do XML.
Totais (manchete) vem do relatorio PDF, nunca recalculados.
"""
import zipfile, json, sys, os, glob, unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ---------- helpers ----------
def load_xml(pjc_path):
    z = zipfile.ZipFile(pjc_path)
    inner = [n for n in z.namelist() if n.upper().endswith(('.PJC', '.XML'))]
    if not inner:
        raise ValueError("sem XML interno no .PJC")
    return ET.fromstring(z.read(inner[0]).decode('iso-8859-1'))

def txt(el, tag):
    if el is None: return None
    c = el.find(tag)
    return c.text.strip() if (c is not None and c.text) else None

def parent_with_child(root, tag):
    """primeiro elemento que tem um filho DIRETO chamado `tag`."""
    for el in root.iter():
        if el.find(tag) is not None:
            return el
    return None

def to_date(ms):
    if ms is None or ms in ('null', ''): return None
    try:
        return datetime.fromtimestamp(int(ms)/1000, tz=timezone.utc).strftime('%Y-%m-%d')
    except Exception:
        return None

def norm(s):
    if s is None: return ''
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return ' '.join(s.upper().split())

# ---------- extracao dos parametros globais ----------
# chave do checkpoint -> como achar no XML
def extract(pjc_path):
    root = load_xml(pjc_path)
    g = {}
    # filhos diretos do root
    for k in ['dataAdmissao','dataDemissao','dataAjuizamento','valorMaiorRemuneracao',
              'valorCargaHorariaPadrao','sabadoDiaUtil','prescricaoQuinquenal','prescricaoFgts']:
        c = root.find(k)
        g[k] = c.text.strip() if (c is not None and c.text) else None
    # bloco de correcao trabalhista (ancora: indiceTrabalhista)
    corr = parent_with_child(root, 'indiceTrabalhista')
    for k in ['indiceTrabalhista','combinarOutroIndice','outroIndiceTrabalhista','apartirDeOutroIndice']:
        g[k] = txt(corr, k)
    # FGTS
    fg = root.find('.//fgts/Fgts')
    g['fgtsAliquota'] = txt(fg, 'aliquota')
    g['incidenciaDoFgts'] = txt(fg, 'incidenciaDoFgts')
    g['multaDoFgts'] = txt(fg, 'multaDoFgts')
    g['excluirAvisoDaMulta'] = txt(fg, 'excluirAvisoDaMulta')
    # INSS / SAT-RAT (ancora: aliquotaRATFixa)
    inss = parent_with_child(root, 'aliquotaRATFixa')
    g['aliquotaRATFixa'] = txt(inss, 'aliquotaRATFixa')
    g['aliquotaEmpresaFixa'] = txt(inss, 'aliquotaEmpresaFixa')
    g['apurarRATPorAtividade'] = txt(inss, 'apurarRATPorAtividade')
    # IRPF
    irpf = parent_with_child(root, 'apurarImpostoRenda')
    g['apurarImpostoRenda'] = txt(irpf, 'apurarImpostoRenda')
    # Custas
    cust = root.find('.//custasJudiciais/CustasJudiciais')
    g['valorConhecimentoDoReclamado'] = txt(cust, 'valorConhecimentoDoReclamado')
    # datas -> YYYY-MM-DD
    for k in ['dataAdmissao','dataDemissao','dataAjuizamento','apartirDeOutroIndice']:
        g[k] = to_date(g[k])
    g['_verbas'] = extract_verbas(root)
    g['_verbas_principais'] = extract_verbas_principais(root)
    return g

def extract_verbas_principais(root):
    """
    Retorna lista de {descricao, base, devido} das verbas <Calculada> (NAO Reflexo).
    Soma APENAS ocorrencias diretas (OcorrenciaDeVerba) em verba/ocorrencias/.
    NAO usa .iter() na verba inteira (duplicaria via <calculo><Calculo> aninhado).
    Espelha build_gabarito.py:verbas_principais() e corretor.js:extractVerbasPrincipais().
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
    """config por verba (Calculada/Reflexo sob <verbas>). Exato, sem somar valor."""
    out = {}
    vroot = root.find('.//verbas')
    if vroot is None: return out
    for el in vroot.iter():
        if el.tag in ('Calculada', 'Reflexo') and el.find('descricao') is not None:
            desc = txt(el, 'descricao')
            key = norm(desc)
            if key in out:  # evita duplicata aninhada
                continue
            out[key] = {
                'tipo': el.tag,
                'descricao': desc,
                'nome': txt(el, 'nome'),
                'incidenciaINSS': txt(el, 'incidenciaINSS'),
                'incidenciaIRPF': txt(el, 'incidenciaIRPF'),
                'incidenciaFGTS': txt(el, 'incidenciaFGTS'),
                'caracteristica': txt(el, 'caracteristica'),
                'comporPrincipal': txt(el, 'comporPrincipal'),
                'aplicarProporcionalidade': txt(el, 'aplicarProporcionalidade'),
                'periodoInicial': to_date(txt(el, 'periodoInicial')),
                'periodoFinal': to_date(txt(el, 'periodoFinal')),
            }
    return out

# ---------- comparacao ----------
def cmp_val(tipo, aluno, esperado, tol):
    if aluno is None: return 'AUSENTE'
    if tipo == 'numero':
        try:
            return 'OK' if abs(round(float(aluno),2) - round(float(esperado),2)) <= float(tol) else 'DIVERGENTE'
        except Exception:
            return 'DIVERGENTE'
    a = norm(str(aluno)); e = norm(str(esperado))
    return 'OK' if a == e else 'DIVERGENTE'

def grade(student_flat, gab, totais_aluno=None):
    boletim = []
    peso_ok = peso_tot = 0.0
    for ck in gab['checkpoints']:
        st = cmp_val(ck.get('tipo','texto'), student_flat.get(ck['key']),
                     ck['esperado'], ck.get('tolerancia',0))
        peso = ck.get('peso',1); peso_tot += peso
        if st == 'OK': peso_ok += peso
        boletim.append({'dimensao':ck['dimensao'],'label':ck['label'],'key':ck['key'],
                        'status':st,'seu_valor':student_flat.get(ck['key']),'dica':ck.get('dica','')})

    # verbas_anchor: compara base de calculo das verbas principais (entra na nota)
    anchors = gab.get('verbas_anchor', [])
    if anchors and gab.get('verba_check', True) is not False:
        aluno_vps = student_flat.get('_verbas_principais', [])
        for anchor in anchors:
            anchor_base = anchor['base']
            peso = anchor.get('peso', 5)
            peso_tot += peso
            # procura verba do aluno cuja base casa com a ancora
            melhor = None
            melhor_diff = None
            for vp in aluno_vps:
                diff = abs(vp['base'] - anchor_base)
                rel = diff / anchor_base if anchor_base else diff
                if melhor_diff is None or diff < melhor_diff:
                    melhor = vp
                    melhor_diff = diff
            # verifica tolerancia: abs <= 0.05 OU rel <= 0.5%
            if melhor is not None:
                diff = abs(melhor['base'] - anchor_base)
                rel = diff / anchor_base if anchor_base else diff
                casa = (diff <= 0.05) or (rel <= 0.005)
            else:
                casa = False
            st = 'OK' if casa else 'DIVERGENTE'
            if st == 'OK':
                peso_ok += peso
            boletim.append({
                'dimensao': 2,
                'label': 'Base de cálculo de verba principal',
                'key': f'verba_anchor_{anchor["label"][:30]}',
                'status': st,
                'seu_valor': melhor['base'] if melhor is not None else None,
                'dica': 'D2 — Verbas deferidas apuradas: base de cálculo deve ser a correta',
            })

    # totais (RESULTADO) — vindos do relatorio PDF; entram na nota. O resultado e a
    # verdade-terra: reflexo a mais / base errada inflam o Total Devido. So o que existe
    # nos dois (gabarito.totais x totais do aluno) e graduado.
    TOTAIS_GRADE = [
        ('totalDevidoReclamado', 'Resultado — Total Devido pelo Reclamado'),
        ('brutoReclamante',      'Resultado — Bruto Devido ao Reclamante'),
        ('liquidoReclamante',    'Resultado — Líquido Devido ao Reclamante'),
    ]
    gab_totais = gab.get('totais', {})
    peso_total = gab.get('peso_total', 4)
    if totais_aluno:
        for key, label in TOTAIS_GRADE:
            esp = gab_totais.get(key); al = totais_aluno.get(key)
            if esp is None or al is None:
                continue
            peso_tot += peso_total
            diff = abs(float(al) - float(esp))
            rel = diff/abs(esp) if esp else diff
            casa = (diff <= 0.05) or (rel <= 0.005)
            if casa: peso_ok += peso_total
            boletim.append({'dimensao': 2, 'label': label, 'key': f'total_{key}',
                            'status': 'OK' if casa else 'DIVERGENTE', 'seu_valor': al,
                            'dica': 'Resultado final: o total nao confere. Reveja reflexos, base de calculo e indice no PJe-Calc.'})

    nota_calc = round(10*peso_ok/peso_tot, 1) if peso_tot else 0.0

    # verbas: diagnostico de montagem (NAO entra na nota — estrutura varia legitimamente)
    verba_diag = []
    sv = student_flat.get('_verbas', {})
    for gk, gv in gab.get('_verbas_gab', {}).items():
        a = sv.get(gk)
        if a is None:
            verba_diag.append({'verba':gv['descricao'],'status':'NAO_ENCONTRADA',
                               'detalhe':'verba nao montada com essa descricao (pode ter sido montada de outro jeito)'})
            continue
        difs = []
        for f in ['incidenciaINSS','incidenciaIRPF','incidenciaFGTS','tipo']:
            if norm(str(a.get(f))) != norm(str(gv.get(f))):
                difs.append(f)
        verba_diag.append({'verba':gv['descricao'],
                           'status':'OK' if not difs else 'CONFERIR','campos_divergentes':difs})
    return {'nota_calculo':nota_calc,'peso_ok':peso_ok,'peso_tot':peso_tot,
            'boletim':boletim,'verbas':verba_diag}

# ---------- self-check + corpus ----------
def main():
    base = os.path.dirname(os.path.abspath(__file__))
    proj = os.path.dirname(base)
    gab = json.load(open(os.path.join(proj,'exercicios','marco16','gabarito.json'),encoding='utf-8'))
    gab_pjc = os.path.join(base,'gabarito','GABARITO.PJC')
    gabflat = extract(gab_pjc)
    gab['_verbas_gab'] = gabflat['_verbas']

    print("===== SELF-CHECK: engine reproduz o gabarito? =====")
    bad = 0
    for ck in gab['checkpoints']:
        got = gabflat.get(ck['key'])
        st = cmp_val(ck.get('tipo','texto'), got, ck['esperado'], ck.get('tolerancia',0))
        if st != 'OK':
            bad += 1
            print(f"  FALHA {ck['key']}: engine={got!r} esperado={ck['esperado']!r}")
    print(f"  {'OK — todos os 21 reproduzem' if bad==0 else str(bad)+' divergencias'}")
    print(f"  verbas do gabarito: {len(gabflat['_verbas'])} -> {list(gabflat['_verbas'].keys())}")

    # corpus de alunos
    target = sys.argv[1] if len(sys.argv)>1 else None
    if not target: return
    pjcs = glob.glob(os.path.join(target,'**','*.PJC'), recursive=True)
    print(f"\n===== CORPUS: {len(pjcs)} .PJC em {target} =====")
    print(f"{'ALUNO':40} {'NOTA':>5} {'OK/TOT':>8}  divergencias")
    rows=[]
    for p in sorted(pjcs):
        try:
            sf = extract(p)
            r = grade(sf, gab)
            div = [b['key'] for b in r['boletim'] if b['status']!='OK']
            who = os.path.basename(os.path.dirname(p))[:39]
            print(f"{who:40} {r['nota_calculo']:5.1f} {int(r['peso_ok'])}/{int(r['peso_tot']):>3}  {', '.join(div[:6])}")
            rows.append((who, r['nota_calculo'], div))
        except Exception as e:
            print(f"{os.path.basename(os.path.dirname(p))[:39]:40}  ERRO: {e}")
    return rows

if __name__ == '__main__':
    main()
