@echo off
REM Sobe o servidor a partir da RAIZ do projeto (pasta deste .bat) e abre o app no navegador.
cd /d "%~dp0"
REM serve.py = no-store (o http.server puro deixava o navegador usar app.js VELHO do cache)
start "Corretor de Impugnacao - SERVIDOR (nao feche esta janela)" cmd /k "python serve.py 8000"
timeout /t 2 /nobreak >nul
start "" "http://localhost:8000/app/?ex=marco16"
echo App aberto no navegador. Para parar, feche a janela do servidor.
