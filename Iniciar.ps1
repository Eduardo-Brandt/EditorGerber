$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Ambiente virtual ausente. Siga as instruções de instalação no README.md.'
}
Start-Process -FilePath $projectPython -ArgumentList '-m', 'gerber_editor' -WorkingDirectory $PSScriptRoot -WindowStyle Normal
