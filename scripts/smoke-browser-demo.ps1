# BOM Risk Analyzer v3.2 browser demo smoke test
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\smoke-browser-demo.ps1

$ErrorActionPreference = "Stop"

function Assert-HttpOk {
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [Parameter(Mandatory=$true)][string]$Name,
        [string]$MustContain = ""
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
    } catch {
        throw "$Name unreachable: $Url; $($_.Exception.Message)"
    }

    if ($response.StatusCode -ne 200) {
        throw "$Name returned HTTP $($response.StatusCode): $Url"
    }

    if ($MustContain -and ($response.Content -notmatch [regex]::Escape($MustContain))) {
        throw "$Name response does not contain expected text '$MustContain': $Url"
    }

    Write-Host "OK $Name -> HTTP $($response.StatusCode)" -ForegroundColor Green
    return $response
}

Write-Host "Running v3.2 browser demo smoke test..." -ForegroundColor Cyan

$backend = Assert-HttpOk -Url "http://127.0.0.1:8001/api/health" -Name "backend health"
$frontend = Assert-HttpOk -Url "http://127.0.0.1:9000/" -Name "frontend home" -MustContain 'id="app"'
$proxy = Assert-HttpOk -Url "http://127.0.0.1:9000/api/health" -Name "frontend api proxy"

Write-Host "Browser demo smoke test passed." -ForegroundColor Green
Write-Host "Open http://127.0.0.1:9000/ and upload demo\sample-bom-v32.csv." -ForegroundColor Green
