@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto fallo
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fallo
".venv\Scripts\python.exe" seed.py
if errorlevel 1 goto fallo
echo.
echo Abri http://localhost:5000 en el navegador.
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto fallo
exit /b 0
:fallo
echo No se pudo iniciar. Revisa el mensaje anterior y que Python este instalado.
pause
exit /b 1
