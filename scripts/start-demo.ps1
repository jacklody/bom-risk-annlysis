# BOM Risk Analyzer v3.2 demo starter
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\start-demo.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$ViteCmd = Join-Path $FrontendDir "node_modules\.bin\vite.cmd"

if (-not (Test-Path -LiteralPath $BackendDir)) {
    throw "backend folder not found: $BackendDir"
}
if (-not (Test-Path -LiteralPath $FrontendDir)) {
    throw "frontend folder not found: $FrontendDir"
}
if (-not (Test-Path -LiteralPath $ViteCmd)) {
    throw "frontend dependencies not found. Please run npm install in frontend folder first."
}

Write-Host "Starting BOM Risk Analyzer v3.2 demo..." -ForegroundColor Cyan
Write-Host "Backend:  http://127.0.0.1:8001/api/health" -ForegroundColor White
Write-Host "Frontend: http://127.0.0.1:9000/" -ForegroundColor White
Write-Host "Sample BOM: demo\sample-bom-v32.csv" -ForegroundColor White

$backendCommand = "Set-Location '$BackendDir'; py -3.11 -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload"
$frontendCommand = "Set-Location '$FrontendDir'; & '$ViteCmd' --host 127.0.0.1 --port 9000"

Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand

Write-Host "Demo services are starting in two PowerShell windows." -ForegroundColor Green
Write-Host "Open http://127.0.0.1:9000/ and upload demo\sample-bom-v32.csv." -ForegroundColor Green
Write-Host "After both services are ready, run: powershell -ExecutionPolicy Bypass -File .\scripts\smoke-browser-demo.ps1" -ForegroundColor Green
Write-Host "For full browser E2E acceptance, run: powershell -ExecutionPolicy Bypass -File .\scripts\e2e-browser-demo.ps1" -ForegroundColor Green
