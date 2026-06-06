param(
    [ValidateSet("auto", "stream", "api", "rag", "agent", "providers", "smoke")]
    [string] $Suite = "stream",

    [string[]] $Target = @(),

    [int] $TimeoutSeconds = 120,

    [switch] $VerbosePytest
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    $localPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"
    if (Test-Path $localPython) {
        return $localPython
    }
    return "python"
}

function Resolve-PytestArgs {
    param(
        [string] $SuiteName,
        [string[]] $ExplicitTargets,
        [switch] $UseVerbose,
        [string] $Python
    )

    $pytestArgs = @("-m", "pytest")
    $normalizedTargets = @(Resolve-ExplicitTargets -ExplicitTargets $ExplicitTargets)
    if ($normalizedTargets.Count -gt 0) {
        $pytestArgs += $normalizedTargets
    } elseif ($SuiteName -eq "auto") {
        $pytestArgs += Resolve-AutoTargets -Python $Python
    } else {
        switch ($SuiteName) {
            "stream" {
                $pytestArgs += @(
                    "tests/test_runtime_api.py::test_chat_knowledge_flow",
                    "tests/test_runtime_api.py::test_chat_knowledge_stream_flow",
                    "tests/test_runtime_api.py::test_chat_stream_returns_error_event_for_generation_errors"
                )
            }
            "api" {
                $pytestArgs += "tests/test_runtime_api.py"
            }
            "rag" {
                $pytestArgs += @(
                    "tests/test_rag_quality.py",
                    "tests/test_interview_artifacts.py"
                )
            }
            "agent" {
                $pytestArgs += "tests/test_agent_workflow.py"
            }
            "providers" {
                $pytestArgs += @(
                    "tests/test_provider_extensions.py",
                    "tests/test_speech_provider_extensions.py",
                    "tests/test_openai_prompt_sanitization.py"
                )
            }
            "smoke" {
                $pytestArgs += @(
                    "tests/test_builtin_plugins.py",
                    "tests/test_routing_enhancements.py",
                    "tests/test_response_enhancement.py",
                    "tests/test_rate_limit_subject.py"
                )
            }
        }
    }

    if ($UseVerbose) {
        $pytestArgs += @("-vv", "-s")
    } else {
        $pytestArgs += "-q"
    }
    return $pytestArgs
}

function Resolve-ExplicitTargets {
    param(
        [string[]] $ExplicitTargets
    )

    $targets = @()
    foreach ($target in $ExplicitTargets) {
        foreach ($item in ($target -split ",")) {
            $trimmed = $item.Trim()
            if ($trimmed) {
                $targets += $trimmed
            }
        }
    }
    return [string[]] $targets
}

function Resolve-AutoTargets {
    param(
        [string] $Python
    )

    $selectorPath = Join-Path (Get-Location) "scripts\select_fast_tests.py"
    $selectionJson = & $Python $selectorPath --json
    if ($LASTEXITCODE -ne 0) {
        throw "fast test auto selector failed with exit code $LASTEXITCODE"
    }
    $selection = $selectionJson | ConvertFrom-Json
    $targets = @($selection.targets)
    Write-Host "==> auto changed files: $(@($selection.changed_paths).Count)"
    Write-Host "==> auto selected suites: $(@($selection.suites) -join ', ')"
    Write-Host "==> auto reason: $($selection.reason)"
    return [string[]] $targets
}

function Invoke-WithTimeout {
    param(
        [string] $FilePath,
        [string[]] $ArgumentList,
        [int] $Timeout
    )

    $runId = [guid]::NewGuid().ToString("N")
    $stdoutPath = Join-Path $env:TEMP "customer_ai_runtime_test_fast_${runId}_stdout.txt"
    $stderrPath = Join-Path $env:TEMP "customer_ai_runtime_test_fast_${runId}_stderr.txt"
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -ErrorAction SilentlyContinue

    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory (Get-Location) `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -NoNewWindow `
        -PassThru

    if (-not $process.WaitForExit($Timeout * 1000)) {
        $process.Kill()
        Write-Host "==> pytest timed out after ${Timeout}s"
        if (Test-Path $stdoutPath) {
            Get-Content -LiteralPath $stdoutPath
        }
        if (Test-Path $stderrPath) {
            Get-Content -LiteralPath $stderrPath
        }
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
        exit 124
    }

    if (Test-Path $stdoutPath) {
        Get-Content -LiteralPath $stdoutPath
    }
    if (Test-Path $stderrPath) {
        Get-Content -LiteralPath $stderrPath
    }
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
    exit $process.ExitCode
}

$python = Resolve-Python
$pytestArgs = Resolve-PytestArgs `
    -SuiteName $Suite `
    -ExplicitTargets $Target `
    -UseVerbose:$VerbosePytest `
    -Python $python

Write-Host "==> fast test suite: $Suite"
Write-Host "==> timeout: ${TimeoutSeconds}s"
Write-Host "==> command: $python $($pytestArgs -join ' ')"

Invoke-WithTimeout `
    -FilePath $python `
    -ArgumentList $pytestArgs `
    -Timeout $TimeoutSeconds
