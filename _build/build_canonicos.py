# -*- coding: utf-8 -*-
"""build_canonicos.py — gera os gabaritos canônicos do Diagnóstico detalhado (beta).

Pra cada _build/<id>/GABARITO.PJC existente, roda comparar_calculos.carregar()
e grava exercicios/<id>/gabarito_canonico.json (dict canônico do motor).
Também copia comparar_calculos.py pra app/motor/ (fonte única no comparar-calculos).

Uso: python _build/build_canonicos.py
"""
import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FONTE_MOTOR = Path(r"C:\Users\jorge\Documents\CLAUDE\comparar-calculos\comparar_calculos.py")
MOTOR_DIR = RAIZ / "app" / "motor"


def main():
    # 1. copia o motor (fonte única) pra dentro do app
    MOTOR_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FONTE_MOTOR, MOTOR_DIR / "comparar_calculos.py")
    print(f"motor copiado -> {MOTOR_DIR / 'comparar_calculos.py'}")

    sys.path.insert(0, str(MOTOR_DIR))
    import comparar_calculos as C

    # 2. canônico de cada exercício que tem GABARITO.PJC
    for exdir in sorted((RAIZ / "exercicios").iterdir()):
        if not exdir.is_dir():
            continue
        pjc = RAIZ / "_build" / exdir.name / "GABARITO.PJC"
        if not pjc.exists():
            print(f"{exdir.name}: sem GABARITO.PJC — pulado (card beta não aparece)")
            continue
        canon = C.carregar(pjc)
        out = exdir / "gabarito_canonico.json"
        out.write_text(json.dumps(canon, ensure_ascii=False), encoding="utf-8")
        print(f"{exdir.name}: {out.name} gerado ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
