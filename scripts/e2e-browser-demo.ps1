# BOM Risk Analyzer v3.2 browser E2E demo test
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\e2e-browser-demo.ps1

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $Root "frontend"
$SmokeScript = Join-Path $PSScriptRoot "smoke-browser-demo.ps1"

if (-not (Test-Path -LiteralPath $FrontendDir)) {
    throw "Frontend directory not found: $FrontendDir"
}

if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "package.json"))) {
    throw "package.json not found in frontend directory: $FrontendDir"
}

Write-Host "Running browser smoke test before E2E..." -ForegroundColor Cyan
& powershell -ExecutionPolicy Bypass -File $SmokeScript

Push-Location $FrontendDir
try {
    $playwrightCmd = Join-Path $FrontendDir "node_modules\.bin\playwright.cmd"
    if (-not (Test-Path -LiteralPath $playwrightCmd)) {
        Write-Host "Playwright dependency is missing. Running npm install..." -ForegroundColor Yellow
        npm install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed; cannot run browser E2E."
        }
    }

    Write-Host "Running Playwright v3.2 browser E2E demo loop..." -ForegroundColor Cyan
    npm run test:e2e
} finally {
    Pop-Location
}
