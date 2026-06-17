param(
    [int] $TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"

$scriptsDir = $PSScriptRoot

Write-Host "==> interview smoke: pytest + demo"
& powershell -ExecutionPolicy Bypass -File (Join-Path $scriptsDir "test-fast.ps1") -Suite rag -TimeoutSeconds $TimeoutSeconds
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& powershell -ExecutionPolicy Bypass -File (Join-Path $scriptsDir "interview-demo.ps1") -Json
exit $LASTEXITCODE
