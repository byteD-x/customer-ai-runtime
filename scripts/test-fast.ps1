param(
    [ValidateSet("stream", "api", "rag", "agent", "providers", "smoke")]
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
        [switch] $UseVerbose
    )

    $pytestArgs = @("-m", "pytest")
    if ($ExplicitTargets.Count -gt 0) {
        $pytestArgs += $ExplicitTargets
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
    -UseVerbose:$VerbosePytest

Write-Host "==> fast test suite: $Suite"
Write-Host "==> timeout: ${TimeoutSeconds}s"
Write-Host "==> command: $python $($pytestArgs -join ' ')"

Invoke-WithTimeout `
    -FilePath $python `
    -ArgumentList $pytestArgs `
    -Timeout $TimeoutSeconds
