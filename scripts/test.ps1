$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Label,

        [Parameter(Mandatory = $true)]
        [string[]] $Command
    )

    Write-Host "==> $Label"
    & $Command[0] $Command[1..($Command.Length - 1)]
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Invoke-CheckedCommand "compileall" @(".venv\Scripts\python.exe", "-m", "compileall", "-q", "src", "tests")
Invoke-CheckedCommand "ruff check" @(".venv\Scripts\python.exe", "-m", "ruff", "check", ".")
Invoke-CheckedCommand "ruff format check" @(".venv\Scripts\python.exe", "-m", "ruff", "format", "--check", ".")
Invoke-CheckedCommand "mypy" @(".venv\Scripts\python.exe", "-m", "mypy", "src")
Invoke-CheckedCommand "pytest" @(".venv\Scripts\python.exe", "-m", "pytest")
