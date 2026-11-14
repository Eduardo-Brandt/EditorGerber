@echo off
setlocal
cd /d "%~dp0"
set "editor_python=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%editor_python%" (
    echo Ambiente virtual ausente. Siga as instrucoes de instalacao no README.md.
    pause
    exit /b 1
)
start "" "%editor_python%" -m gerber_editor %*
if errorlevel 1 (
    echo Nao foi possivel iniciar o Editor Gerber. Consulte output\logs.
    pause
    exit /b 1
)
exit /b 0
