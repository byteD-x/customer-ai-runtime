param(
    [string] $OutputDir = ".codex",
    [string] $OnlineRagSamplePath,
    [double] $ReadinessTimeoutSeconds = 5.0
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    return Split-Path -Parent $PSScriptRoot
}

function Resolve-Python {
    $localPython = Join-Path (Resolve-RepoRoot) ".venv\Scripts\python.exe"
    if (Test-Path $localPython) {
        return $localPython
    }
    return "python"
}

function Invoke-Step {
    param(
        [string] $Label,
        [string] $FilePath,
        [string[]] $ArgumentList
    )

    Write-Host "==> $Label"
    Write-Host "    $FilePath $($ArgumentList -join ' ')"
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Push-Location (Resolve-RepoRoot)
try {
    $python = Resolve-Python
    $resolvedOutputDir = Resolve-Path -LiteralPath $OutputDir -ErrorAction SilentlyContinue
    if ($null -eq $resolvedOutputDir) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
        $resolvedOutputDir = Resolve-Path -LiteralPath $OutputDir
    }
    $outputRoot = $resolvedOutputDir.Path

    $interviewReport = Join-Path $outputRoot "interview-demo-report.md"
    $ragEvalReport = Join-Path $outputRoot "rag-eval-report.json"
    $readinessReport = Join-Path $outputRoot "external-readiness-report.json"
    $onlineEvalReport = Join-Path $outputRoot "online-rag-eval-report.json"

    Invoke-Step `
        -Label "interview markdown report" `
        -FilePath "powershell" `
        -ArgumentList @(
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts\interview-demo.ps1",
            "-Markdown",
            "-OutputPath",
            $interviewReport
        )

    Invoke-Step `
        -Label "rag eval report" `
        -FilePath $python `
        -ArgumentList @(
            "scripts\eval_rag.py",
            "--json",
            "--output",
            $ragEvalReport
        )

    Invoke-Step `
        -Label "external readiness report" `
        -FilePath $python `
        -ArgumentList @(
            "scripts\check_external_readiness.py",
            "--json",
            "--timeout",
            "$ReadinessTimeoutSeconds",
            "--output",
            $readinessReport
        )

    $generated = @($interviewReport, $ragEvalReport, $readinessReport)
    if ($OnlineRagSamplePath) {
        Invoke-Step `
            -Label "online rag eval report" `
            -FilePath $python `
            -ArgumentList @(
                "scripts\eval_online_rag.py",
                $OnlineRagSamplePath,
                "--json",
                "--output",
                $onlineEvalReport
            )
        $generated += $onlineEvalReport
    }

    Write-Host "==> interview package generated"
    foreach ($path in $generated) {
        Write-Host "    $path"
    }
}
finally {
    Pop-Location
}
