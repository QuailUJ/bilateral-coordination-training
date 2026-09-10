$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDir
$probe = "import sys, struct; sys.exit(0 if sys.version_info[:2] == (3,11) and struct.calcsize('P') == 8 else 1)"

function Test-Python([string]$Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    try {
        & $Path -c $probe 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

function Find-Python {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            $candidate = & $launcher.Source -3.11 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and (Test-Python $candidate)) { return $candidate }
        } catch {}
    }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
        (Join-Path $env:ProgramFiles 'Python311\python.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Python $candidate) { return $candidate }
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike '*\WindowsApps\*' -and (Test-Python $command.Source)) {
        return $command.Source
    }
    return $null
}

try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw '64-bit Windows is required.' }
    if (-not (Test-Path -LiteralPath 'requirements.txt')) { throw 'Extract the entire project ZIP first.' }
    Write-Host '[1/4] Checking Python 3.11 (64-bit)...'
    $venvPython = Join-Path $projectDir '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath '.venv') {
        if (-not (Test-Python $venvPython)) {
            throw 'Existing .venv is invalid or incompatible. Rename .venv and run install.bat again.'
        }
    } else {
        $python = Find-Python
        if (-not $python) {
            Write-Host 'Downloading Python 3.11.9 from python.org...'
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            $downloadDir = Join-Path ([IO.Path]::GetTempPath()) ('bilateral-python-' + [guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Path $downloadDir | Out-Null
            $installer = Join-Path $downloadDir 'python-3.11.9-amd64.exe'
            $downloadUrl = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe'
            $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
            if ($curl) {
                & $curl.Source --fail --location --connect-timeout 20 --max-time 300 --output $installer $downloadUrl
                if ($LASTEXITCODE -ne 0) { throw 'Python download failed. Check your Internet connection and retry.' }
            } else {
                Invoke-WebRequest -UseBasicParsing -TimeoutSec 300 -Uri $downloadUrl -OutFile $installer
            }
            $signature = Get-AuthenticodeSignature -LiteralPath $installer
            if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
                throw 'Python installer signature verification failed.'
            }
            Write-Host 'Installing Python for the current Windows user...'
            $process = Start-Process -FilePath $installer -ArgumentList @('/quiet', 'InstallAllUsers=0', 'Include_launcher=0', 'Include_test=0', 'Include_pip=1', 'PrependPath=0') -Wait -PassThru -WindowStyle Hidden
            if ($process.ExitCode -notin @(0, 3010)) { throw "Python installer failed: $($process.ExitCode)" }
            $python = Find-Python
            if (-not $python) { throw 'Python was not detected. Restart Windows and run install.bat again.' }
        }
        Write-Host '[2/4] Creating the project environment...'
        & $python -m venv (Join-Path $projectDir '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv.' }
    }
    Write-Host '[3/4] Installing packages from requirements.txt...'
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed. Check your Internet connection and retry.' }
    & $venvPython -m pip install -r (Join-Path $projectDir 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Package installation failed. See the error above and retry.' }
    Write-Host '[4/4] Checking installation...'
    & $venvPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Package compatibility check failed.' }
    & $venvPython -c 'import pygame, cv2, mediapipe, numpy, PIL; import main, elbow_angle_tracker'
    if ($LASTEXITCODE -ne 0) { throw 'Application import check failed.' }
    foreach ($model in @('model\hand_landmarker.task', 'model\pose_landmarker_full.task')) {
        if (-not (Test-Path -LiteralPath $model -PathType Leaf)) {
            throw "Missing model: $model. Extract the entire project ZIP again."
        }
    }
    Write-Host ''
    Write-Host 'Installation complete! Double-click start_game.bat or start_elbow.bat.' -ForegroundColor Green
    exit 0
} catch {
    Write-Host ''
    Write-Host ('Installation failed: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Keep this window message for troubleshooting. You can run install.bat again.'
    exit 1
}
