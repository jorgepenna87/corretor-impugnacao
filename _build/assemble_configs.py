# -*- coding: utf-8 -*-
"""
assemble_configs.py — monta _build/<id>/config.json a partir de:
  - metadados do exercicio (abaixo)
  - conjunto PADRAO de checkpoints (mesmo do marco16), filtrando o que nao se aplica
  - textChecklist vindo de _build/mentoria/<id>_temas.json (tema, dimensao, keywords, explicacao_curta)
  - totais_hardcoded verificados do relatorio
Roda 1x; depois usa-se build_gabarito.py para gerar exercicios/<id>/gabarito.json.
"""
import json, os

BUILD = os.path.dirname(os.path.abspath(__file__))

# ---- conjunto PADRAO de checkpoints (key, dimensao, label, tipo, tolerancia, peso, dica) ----
STD = [
    ("dataAdmissao", 1, "Data de admissão", "data", 0, 1, "D1 — Período de cálculo: data de admissão"),
    ("dataDemissao", 1, "Data de demissão", "data", 0, 1, "D1 — Período de cálculo: data de demissão"),
    ("dataAjuizamento", 1, "Data de ajuizamento", "data", 0, 1, "D1 — Data de ajuizamento define o divisor de correção/juros (ADC 58 / Lei 14.905)"),
    ("valorMaiorRemuneracao", 5, "Maior remuneração (base de cálculo)", "numero", 0.05, 2, "D5 — Divisor e maior remuneração: base de todas as verbas"),
    ("valorCargaHorariaPadrao", 5, "Carga horária padrão (divisor)", "numero", 0, 1, "D5 — Carga horária/divisor impacta horas extras e adicional noturno"),
    ("sabadoDiaUtil", 5, "Sábado como dia útil", "booleano", 0, 1, "D5 — Sábado dia útil altera contagem de DSR e aviso prévio"),
    ("indiceTrabalhista", 16, "Índice de correção monetária principal", "texto", 0, 3, "D16 — Juros e correção: índice correto por ADC 58 (IPCA-E até o ajuizamento)"),
    ("combinarOutroIndice", 16, "Combinar segundo índice a partir do ajuizamento", "booleano", 0, 2, "D16 — ADC 58 / Lei 14.905: IPCA-E até o ajuizamento; a partir daí SELIC (já engloba juros+correção)"),
    ("outroIndiceTrabalhista", 16, "Segundo índice (a partir do ajuizamento)", "texto", 0, 2, "D16 — Após o ajuizamento, a SELIC engloba correção: o índice de correção adicional deve ser 'SEM_CORRECAO'"),
    ("apartirDeOutroIndice", 16, "Data de início do segundo índice", "data", 0, 1, "D16 — Data divisor (ADC 58): deve coincidir com o ajuizamento"),
    ("fgtsAliquota", 17, "Alíquota FGTS", "texto", 0, 1, "D17 — Base FGTS: alíquota padrão 8%"),
    ("incidenciaDoFgts", 17, "Incidência do FGTS", "texto", 0, 1, "D17 — Base FGTS: sobre o total devido ou sobre a diferença, conforme a sentença"),
    ("multaDoFgts", 18, "Multa do FGTS (40%)", "texto", 0, 1, "D18 — Base multa 40%: percentual correto"),
    ("excluirAvisoDaMulta", 18, "Excluir aviso prévio da base da multa", "booleano", 0, 1, "D18 — Aviso prévio indenizado entra ou não na base da multa 40%"),
    ("aliquotaEmpresaFixa", 21, "Alíquota INSS empresa (20%)", "numero", 0, 1, "D21 — INSS empresa: 20% regime geral (ou % diferente se SIMPLES/desonerado)"),
    ("aliquotaRATFixa", 22, "Alíquota SAT/RAT", "numero", 0, 2, "D22 — SAT/RAT pelo CNAE: alíquota correta conforme a atividade"),
    ("apurarRATPorAtividade", 22, "Apurar RAT por atividade (CNAE)", "booleano", 0, 1, "D22 — Se true, o sistema usa a alíquota do CNAE; se false, usa a fixada"),
    ("apurarImpostoRenda", 20, "Apurar IRPF", "booleano", 0, 1, "D20 — IRPF: deve ser apurado pelo regime RRA (rendimentos acumulados)"),
    ("valorConhecimentoDoReclamado", 23, "Custas pagas pelo Reclamado", "numero", 0.05, 1, "D23 — Custas judiciais deduzidas: valor informado"),
    ("prescricaoQuinquenal", 1, "Aplicar prescrição quinquenal", "booleano", 0, 1, "D1 — Prescrição quinquenal (5 anos)"),
    ("prescricaoFgts", 1, "Aplicar prescrição específica de FGTS", "booleano", 0, 1, "D1 — Prescrição específica do FGTS"),
]


def cp_defs(drop=()):
    out = []
    for key, dim, label, tipo, tol, peso, dica in STD:
        if key in drop:
            continue
        out.append({"key": key, "dimensao": dim, "label": label, "tipo": tipo,
                    "tolerancia": tol, "peso": peso, "dica": dica})
    return out


def text_checklist(exid):
    temas = json.load(open(os.path.join(BUILD, "mentoria", f"{exid}_temas.json"), encoding="utf-8"))
    out = []
    for t in temas:
        out.append({
            "tema": t["tema"],
            "dimensao": t["dimensao"],
            "keywords": t["keywords"],
            "explicacao_curta": t.get("explicacao_curta", ""),
        })
    return out


EXS = {
    "abril13": {
        "exercicio": {
            "id": "abril13",
            "titulo": "Exercício Abril/13 — Impugnação de Cálculo (Ótica Reclamada)",
            "processo": "0101079-18.2024.5.01.0005",
            "otica": "RECLAMADA",
            "descricao": "Caso RENATO ALVES DE OLIVEIRA x JOALHERIA SANTA TRINDADE. O aluno recebe o cálculo do autor e deve impugná-lo, refazendo no PJe-Calc com os parâmetros corretos.",
        },
        "drop": (),
        "totais_hardcoded": {
            "totalDevidoReclamado": 150853.03,
            "brutoReclamante": 129838.50,
            "inssEmpresa": 13102.71,
            "multaFGTS": 8221.66,
            "custas": 600.60,
        },
    },
    "junho22": {
        "exercicio": {
            "id": "junho22",
            "titulo": "Exercício Junho/22 — Impugnação de Cálculo (Ótica Reclamada)",
            "processo": "0100333-87.2023.5.01.0005",
            "otica": "RECLAMADA",
            "descricao": "Caso MÁRCIO DUARTE FONSECA x COMERCIAL VEROCITY (comissionista, horas extras e intervalo). O aluno recebe o cálculo do autor e deve impugná-lo, refazendo no PJe-Calc.",
        },
        # custas sao FIXADAS EM SENTENCA. So ha impugnacao a fazer quando o reclamante as
        # apura A MAIOR que o valor fixado (a reclamada impugna o excesso). Aqui o reclamante
        # apurou 1.353,44 = exatamente a sentenca (2% x 67.672,00) -> NAO foi a maior -> nada
        # a impugnar -> remove o checkpoint. (Regra: custas e checkpoint so quando autor > sentenca.)
        "drop": ("valorConhecimentoDoReclamado",),
        # verba_check OFF: alunos reestruturam as verbas (comissionista/RSR/HE) de forma
        # radicalmente diferente do gabarito -> anchor-por-valor falha em massa e nao da pra
        # distinguir erro real de montagem legitima sem revisao do Jorge. Reavaliar caso a caso.
        "verba_check": False,
        "totais_hardcoded": {
            "totalDevidoReclamado": 518501.20,
            "brutoReclamante": 425048.56,
            "liquidoReclamante": 354974.95,
            "inssEmpresa": 68673.63,
            "multaFGTS": 11949.83,
            "custas": 1353.44,
        },
    },
    "setembro15": {
        "exercicio": {
            "id": "setembro15",
            "titulo": "Exercício Setembro/15 — Impugnação de Cálculo (Ótica Reclamada)",
            "processo": "0100681-55.2023.5.01.0248",
            "otica": "RECLAMADA",
            "descricao": "Caso GESSI SOARES COSTA (diárias de viagem e diferença salarial por redução unilateral). O aluno recebe o cálculo do autor e deve impugná-lo, refazendo no PJe-Calc.",
        },
        # gabarito nao fixou maior remuneracao nem custas -> remove esses checkpoints
        "drop": ("valorMaiorRemuneracao", "valorConhecimentoDoReclamado"),
        # verba_check OFF: unico aluno (Miguel) reestrutura as diarias em duas verbas e a
        # diferenca salarial de forma diferente do gabarito -> anchor falha sem que de pra
        # confirmar erro real. Reavaliar com o Jorge.
        "verba_check": False,
        "totais_hardcoded": {
            "totalDevidoReclamado": 347646.29,
            "brutoReclamante": 291730.85,
            "multaFGTS": 462.16,
            "honorarios": 14586.54,
        },
    },
}


def main():
    for exid, meta in EXS.items():
        config = {
            "exercicio": meta["exercicio"],
            "tolerancia_verba_percentual": 0.5,
            "peso_verba": meta.get("peso_verba", 5),
            "verba_check": meta.get("verba_check", True),
            "totais_hardcoded": meta["totais_hardcoded"],
            "checkpoints_def": cp_defs(meta["drop"]),
            "textChecklist": text_checklist(exid),
        }
        out = os.path.join(BUILD, exid, "config.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"OK {out}  (checkpoints={len(config['checkpoints_def'])}, temas={len(config['textChecklist'])})")


if __name__ == "__main__":
    main()
