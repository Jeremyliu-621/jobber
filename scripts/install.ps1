param(
    [string]$Workspace = (Join-Path $HOME "Jobber"),
    [string]$Python = "py"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot ".."))
$Venv = Join-Path $ProjectRoot ".venv"

& $Python -3 -m venv $Venv
$VenvPython = Join-Path $Venv "Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e "$ProjectRoot[browser]"
& (Join-Path $Venv "Scripts\job-agent.exe") init $Workspace

Write-Host "Jobber is installed in $Venv"
Write-Host "Workspace selected: $Workspace"
Write-Host "Next: edit $Workspace\candidate\profile.yaml"
Write-Host "Then run: $Venv\Scripts\job-agent.exe web"
