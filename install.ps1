$ErrorActionPreference = "Stop"

$RawUrl = if ($env:MEU_RAW_URL) { $env:MEU_RAW_URL } else { "https://raw.githubusercontent.com/meucak/meu/main/meu.py" }

$PythonCmd = $null
foreach ($cand in @("python", "python3", "py")) {
    $found = Get-Command $cand -ErrorAction SilentlyContinue
    if ($found -and $found.Source -notlike "*WindowsApps*") {
        $PythonCmd = $cand
        break
    }
}
if (-not $PythonCmd) {
    foreach ($cand in @("python", "python3", "py")) {
        if (Get-Command $cand -ErrorAction SilentlyContinue) {
            $PythonCmd = $cand
            break
        }
    }
}

if (-not $PythonCmd) {
    Write-Error "Python 3 bulunamadi. Lutfen https://www.python.org veya winget install Python.Python.3.12 ile kurun."
    exit 1
}

$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$LocalMeu = Join-Path $ScriptDir "meu.py"

if (Test-Path $LocalMeu) {
    if ($PythonCmd -eq "py") {
        & py -3 $LocalMeu self-install
    } else {
        & $PythonCmd $LocalMeu self-install
    }
} else {
    $TempMeu = Join-Path $env:TEMP ("meu_install_" + [guid]::NewGuid().ToString("N") + ".py")
    try {
        Invoke-WebRequest -Uri $RawUrl -OutFile $TempMeu -UseBasicParsing
        if ($PythonCmd -eq "py") {
            & py -3 $TempMeu self-install
        } else {
            & $PythonCmd $TempMeu self-install
        }
    } finally {
        if (Test-Path $TempMeu) { Remove-Item $TempMeu -Force -ErrorAction SilentlyContinue }
    }
}
