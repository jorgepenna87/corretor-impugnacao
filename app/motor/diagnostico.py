# -*- coding: utf-8 -*-
"""diagnostico.py — camada no-spoiler do Diagnóstico detalhado (beta).

Roda em cima do motor comparar_calculos (diff + raiz):
    diagnosticar(aluno_canon, gabarito_canon) -> {"itens": [...], "cascata_qtd": n}

REGRA: o aluno NUNCA vê o valor do gabarito — só o valor DELE + a dimensão
+ a dica de estudo. (A = aluno, B = gabarito; strip total do campo 'b'.)
Não dá nota — a nota oficial continua sendo a do corretor.js.
"""
from comparar_calculos import diff, raiz

# dica pedagógica por dimensão (adaptado do corretor-pjecalc)
DICA_DIM = {
    1: "Confira o PERÍODO de apuração (admissão/demissão/prescrição e o período de cada verba).",
    2: "Confira as VERBAS apuradas: falta verba deferida ou sobra verba não deferida (e os reflexos).",
    4: "Confira os ÍNDICES de correção monetária (ADC 58: IPCA-E até a citação, depois SELIC).",
    5: "Confira o DIVISOR e a maior remuneração.",
    6: "Confira a apuração do CARTÃO DE PONTO: forma de apuração, jornada, tolerância e intervalos.",
    9: "Confira as QUANTIDADES mensais (a soma do cartão diário bate com o que você lançou?).",
    10: "Confira os dias de AVISO PRÉVIO (proporcionalidade da Lei 12.506/2011).",
    11: "Confira a DEDUÇÃO DE PAGOS (valores já recebidos pelo reclamante).",
    12: "Confira os dias de RSR (repouso, feriado, ponto facultativo).",
    13: "Confira as INCIDÊNCIAS por verba (FGTS/INSS/IRPF — verba indenizatória não incide).",
    14: "Confira a BASE DE CÁLCULO da verba (histórico salarial / salário paradigma).",
    15: "Confira a PROPORCIONALIDADE (avos de 13º e férias).",
    16: "Confira os JUROS (taxa, fase pré-judicial, momento de aplicação).",
    17: "Confira a BASE DO FGTS (incidência e alíquota de 8%).",
    18: "Confira a MULTA DE 40% do FGTS.",
    20: "Confira o IRPF (apuração e base).",
    21: "Confira o INSS patronal (alíquota da empresa / Simples / desoneração).",
    22: "Confira o SAT/RAT (alíquota pelo CNAE).",
    23: "Confira as CUSTAS (valor fixado na sentença).",
    25: "Confira o SEGURO-DESEMPREGO: tipo de solicitação, número de parcelas, "
        "salário considerado e as faixas da tabela vigente.",
}


def _no_spoiler_item(x):
    """Item de raiz SEM o valor do gabarito ('b') — só o que o aluno lançou."""
    chave = x.get("chave")
    # D2: dizer a DIREÇÃO (A = aluno, B = gabarito) — 'faltou' x 'a mais/estrutura'
    tipo = x.get("tipo") or ""
    if tipo.startswith("verba a mais"):
        chave = f"{chave} — está no SEU cálculo e não no gabarito (verba a mais, ou montada com outra estrutura: principal × reflexo)"
    elif tipo.startswith("verba faltante"):
        chave = f"{chave} — FALTOU no seu cálculo (ou foi montada com outra estrutura)"
    return {
        "dim": x["dim"],
        "dim_nome": x.get("dim_nome"),
        "chave": chave,
        "seu_valor": x.get("a"),
        "dica": DICA_DIM.get(x["dim"], "Revise este ponto."),
    }


def diagnosticar(aluno, gabarito):
    """A = aluno, B = gabarito. Retorna dict pronto pra UI (no-spoiler)."""
    d = diff(aluno, gabarito)
    r = raiz(d)
    return {
        "itens": [_no_spoiler_item(x) for x in r["raiz"]],
        "cascata_qtd": r["cascata_qtd"],
    }
