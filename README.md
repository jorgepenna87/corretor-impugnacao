# Corretor de Impugnação de Cálculo

App web client-side (zero backend, zero IA) que corrige exercícios de impugnação de
cálculo trabalhista comparando o `.PJC` do aluno contra o gabarito do professor.

A documentação técnica completa (arquitetura, formato `.PJC`, regra no-spoiler, como
gerar um exercício novo) está em [LEIA-ME.md](LEIA-ME.md). Leia antes de mexer no motor.

## Rodar local

O app usa `fetch()`, então não funciona abrindo o `index.html` direto (`file://`).
Sirva a pasta:

```bash
python -m http.server 8000
```

Abra `http://localhost:8000/app/?ex=marco16` (ou `abril13`, `junho22`, `setembro15`).
No Windows, o `start.bat` faz as duas coisas.

Para os scripts de build em `_build/` (Python) e a checagem de paridade (Node):

```bash
npm install
```

## Onde mexer

| Quero...                          | Arquivo                                  |
|-----------------------------------|------------------------------------------|
| mudar a interface                 | `app/index.html`, `app/style.css`, `app/app.js` |
| mudar a regra de correção         | `app/corretor.js` **e** `_build/engine.py` (os dois, sempre) |
| adicionar exercício               | `exercicios/<id>/gabarito.json` (gerado, ver LEIA-ME) |
| mudar o mapa dimensão para aula   | `exercicios/<id>/aulas.json`             |

`corretor.js` (browser) e `engine.py` (fonte da verdade) precisam bater exato.
Toda alteração em regra de correção passa por:

```bash
python _build/exrunner.py all marco16
node _build/parity.cjs marco16
```

O self-check tem que dar 100%. Repita nos quatro exercícios antes de abrir PR.

## Fluxo de trabalho

`main` é a branch estável, a que vai pro ar. Ninguém commita direto nela.

```bash
git checkout -b feat/nome-curto
git commit -m "descrição do que mudou e por quê"
git push -u origin feat/nome-curto
```

Depois abra o Pull Request pro `main`. No PR, cole a saída do `exrunner.py` e do
`parity.cjs` do exercício afetado: é a prova de que o motor continua correto.

## Regra dura: no-spoiler

O app nunca exibe o valor do gabarito. Só o valor que o aluno enviou, o status por
dimensão (OK / REVER / AUSENTE), o ponteiro de estudo e o convite para refazer.
Qualquer PR que vaze valor esperado na interface é rejeitado.
