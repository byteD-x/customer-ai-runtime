param(
    [switch] $Json,
    [switch] $Markdown,
    [string] $StorageRoot
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

Push-Location (Resolve-RepoRoot)
try {
    $python = Resolve-Python
    $args = @("examples\interview_demo.py")
    if ($Json) {
        $args += "--json"
    }
    elseif ($Markdown) {
        $args += "--markdown"
    }
    if ($StorageRoot) {
        $args += @("--storage-root", $StorageRoot)
    }

    Write-Host "==> interview demo: $python $($args -join ' ')"
    & $python @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
