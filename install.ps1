param(
    [string]$InstallRoot = (Get-Location).Path,
    [string]$PythonBin = "python",
    [string]$DistRepo = "https://github.com/LalitYadav07/radar-pd-pip-prototype.git",
    [string]$RawBase = "https://raw.githubusercontent.com/LalitYadav07/radar-pd-pip-prototype/main",
    [string]$AppRepo = "https://github.com/LalitYadav07/Impurity_detection_GSAS_ver6.git"
)

$ErrorActionPreference = "Stop"

$InstallRoot = (Resolve-Path -LiteralPath $InstallRoot).Path
$VenvDir = Join-Path $InstallRoot "env"
$SourceDir = Join-Path $InstallRoot "source"
$CacheDir = Join-Path $InstallRoot "cache"
$BootstrapDir = Join-Path $InstallRoot ".bootstrap"
$PythonInstallDir = Join-Path $BootstrapDir "python"
$UvDir = Join-Path $BootstrapDir "uv"
$RuntimeWheel = "$RawBase/wheelhouse/radar_pd_gsasii_runtime-0.0.1-cp312-cp312-win_amd64.whl"

function Test-Python312 {
    param([string]$Candidate)
    try {
        $version = & $Candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        return $version.Trim() -eq "3.12"
    } catch {
        return $false
    }
}

function Find-Python312 {
    param([string]$Preferred)
    if ($Preferred -and (Get-Command $Preferred -ErrorAction SilentlyContinue)) {
        if (Test-Python312 $Preferred) {
            return (Get-Command $Preferred).Source
        }
    }
    foreach ($candidate in @("python3.12", "py")) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            if ($candidate -eq "py") {
                try {
                    $version = & py -3.12 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
                    if ($version.Trim() -eq "3.12") {
                        return "py -3.12"
                    }
                } catch {}
            } elseif (Test-Python312 $candidate) {
                return (Get-Command $candidate).Source
            }
        }
    }
    return $null
}

function Invoke-Python {
    param(
        [string]$Python,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )
    if ($Python -eq "py -3.12") {
        & py -3.12 @Args
    } else {
        & $Python @Args
    }
}

function Invoke-NativeChecked {
    param(
        [string]$Executable,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )
    & $Executable @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Executable $($Args -join ' ')"
    }
}

New-Item -ItemType Directory -Force -Path $InstallRoot, $CacheDir, $BootstrapDir | Out-Null
$env:RADAR_PD_CACHE_HOME = $CacheDir
$env:UV_NATIVE_TLS = "1"

$Python = Find-Python312 $PythonBin
if (-not $Python) {
    Write-Host "Python 3.12 was not found. Bootstrapping local Python 3.12 with uv under: $PythonInstallDir"
    New-Item -ItemType Directory -Force -Path $UvDir | Out-Null

    $UvExe = Join-Path $UvDir "uv.exe"
    if (-not (Test-Path $UvExe)) {
        $env:UV_UNMANAGED_INSTALL = $UvDir
        Invoke-Expression (Invoke-RestMethod https://astral.sh/uv/install.ps1)
        Remove-Item Env:\UV_UNMANAGED_INSTALL -ErrorAction SilentlyContinue
    }

    Invoke-NativeChecked -Executable $UvExe -Args @("--native-tls", "python", "install", "3.12", "--install-dir", $PythonInstallDir)
    $Python = Get-ChildItem -Path $PythonInstallDir -Filter python.exe -Recurse |
        Where-Object { Test-Python312 $_.FullName } |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $Python) {
        throw "uv installed Python 3.12, but no usable python.exe was found under $PythonInstallDir"
    }
    Write-Host "Using bootstrapped Python: $Python"
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is required to fetch the RADAR-PD source checkout."
}

Write-Host "Creating/updating virtual environment: $VenvDir"
Invoke-Python -Python $Python -Args @("-m", "venv", $VenvDir)
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

& $VenvPython -m pip install --upgrade pip

Write-Host "Installing RADAR-PD prototype from GitHub..."
& $VenvPython -m pip install `
    "radar-pd-gsasii-runtime @ $RuntimeWheel" `
    "radar-pd[app] @ git+$DistRepo#subdirectory=radar_pd"

if (Test-Path (Join-Path $SourceDir ".git")) {
    Write-Host "Updating RADAR-PD source checkout: $SourceDir"
    git -C $SourceDir pull --ff-only
} else {
    Write-Host "Cloning RADAR-PD source checkout: $SourceDir"
    if (Test-Path $SourceDir) {
        Remove-Item -Recurse -Force $SourceDir
    }
    git clone --depth 1 $AppRepo $SourceDir
}

Write-Host "Running GSAS-II smoke diagnostic..."
& (Join-Path $VenvDir "Scripts\radar-pd.exe") doctor --smoke-gsas-project

$LaunchScript = Join-Path $InstallRoot "launch-radar-pd.ps1"
@"
param(
    [int]`$Port = 8501,
    [string]`$Address = "127.0.0.1"
)

function Test-PortAvailable {
    param([int]`$CandidatePort)
    try {
        `$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse(`$Address), `$CandidatePort)
        `$listener.Start()
        `$listener.Stop()
        return `$true
    } catch {
        return `$false
    }
}

if (-not (Test-PortAvailable `$Port)) {
    `$requestedPort = `$Port
    for (`$candidate = 8502; `$candidate -le 8599; `$candidate++) {
        if (Test-PortAvailable `$candidate) {
            `$Port = `$candidate
            break
        }
    }
    if (`$Port -eq `$requestedPort -and -not (Test-PortAvailable `$Port)) {
        throw "No available Streamlit port found in range 8501-8599."
    }
    Write-Host "Port `$requestedPort is busy; using port `$Port instead."
}

`$env:RADAR_PD_CACHE_HOME = "$CacheDir"
Write-Host "Launching RADAR-PD at http://`$Address`:`$Port"
& "$VenvDir\Scripts\radar-pd.exe" ui --source-root "$SourceDir" --address `$Address --port `$Port
"@ | Set-Content -Path $LaunchScript -Encoding UTF8

Write-Host ""
Write-Host "Install complete."
Write-Host ""
Write-Host "Activate:"
Write-Host "  $VenvDir\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Launch GUI:"
Write-Host "  powershell -ExecutionPolicy Bypass -File $LaunchScript"
Write-Host "  powershell -ExecutionPolicy Bypass -File $LaunchScript -Port 8502"
