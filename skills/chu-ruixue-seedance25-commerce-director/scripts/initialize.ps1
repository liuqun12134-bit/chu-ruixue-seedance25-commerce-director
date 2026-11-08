param(
    [switch]$CheckOnly,
    [string]$RuntimeDir,
    [string]$SearchRoot = (Get-Location).Path,
    [string]$PythonPath,
    [string]$ModelDir
)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
if (-not $RuntimeDir) {
    if ($env:CRX_RUNTIME_DIR) { $RuntimeDir = $env:CRX_RUNTIME_DIR }
    else { $RuntimeDir = Join-Path $env:USERPROFILE '.codex\runtimes\chu-ruixue-seedance25-commerce-director' }
}
$RuntimeDir = [IO.Path]::GetFullPath($RuntimeDir)
$scriptPath = Join-Path $PSScriptRoot 'initialize.py'
function Test-Python([string]$Executable) {
    if (-not $Executable -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $false }
    try {
        $result = & $Executable -c "import sys,struct,venv,ssl; print('CRX_OK' if sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 else 'NO')" 2>$null
        return ($LASTEXITCODE -eq 0 -and ($result -contains 'CRX_OK'))
    } catch { return $false }
}
try {
    if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        throw 'Automatic installation supports Windows x64 only; this platform was not modified.'
    }
    $candidates = @($PythonPath)
    $configPath = Join-Path $RuntimeDir 'runtime.json'
    if (Test-Path -LiteralPath $configPath) {
        try { $candidates += (Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json).python } catch {}
    }
    $candidates += (Join-Path $RuntimeDir 'venv\Scripts\python.exe')
    $candidates += (Join-Path $RuntimeDir 'python\python.exe')
    $candidates += (Join-Path $SearchRoot '.tools\local-asr\Scripts\python.exe')
    if ($env:USERPROFILE) {
        $candidates += (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
    }
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        foreach ($version in @('-3.12')) {
            try {
                $found = & $pyCommand.Source $version -c 'import sys; print(sys.executable)' 2>$null
                if ($LASTEXITCODE -eq 0) { $candidates += $found }
            } catch {}
        }
    }
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike '*\WindowsApps\*') { $candidates += $pythonCommand.Source }
    $selected = $null
    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (Test-Python $candidate) { $selected = $candidate; break }
    }
    $bootstrapped = $false
    if (-not $selected) {
        if ($CheckOnly) {
            @{ ok=$false; status='missing'; missing=@('Python 3.12 x64'); message='缺少可用 Python；正式初始化将安装独立 Python 并继续检测其他组件。'; other_components='not_checked' } | ConvertTo-Json -Compress
            exit 2
        }
        Write-Host '未找到兼容 Python，正在安装独立 Python 3.12.10（不修改 PATH）…'
        New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
        $installer = Join-Path $RuntimeDir 'python-3.12.10-amd64.exe'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $installer
        $signature = Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
            throw 'Python installer signature validation failed; installer was not executed.'
        }
        $installTarget = Join-Path $RuntimeDir 'python'
        $arguments = '/quiet InstallAllUsers=0 Include_launcher=0 PrependPath=0 Include_test=0 Include_doc=0 Shortcuts=0 AssociateFiles=0 Include_pip=1 TargetDir="' + $installTarget + '"'
        $process = Start-Process -FilePath $installer -ArgumentList $arguments -WindowStyle Hidden -PassThru
        if (-not $process.WaitForExit(600000)) { throw 'Python installation exceeded ten minutes; inspect the installer before retrying.' }
        if ($process.ExitCode -notin @(0,3010)) { throw "Python installer failed: $($process.ExitCode)" }
        $selected = Join-Path $installTarget 'python.exe'
        if (-not (Test-Python $selected)) { throw 'Installed Python did not pass the runtime check.' }
        $bootstrapped = $true
    }
    $arguments = @($scriptPath, '--runtime-dir', $RuntimeDir, '--search-root', $SearchRoot)
    if ($CheckOnly) { $arguments += '--check-only' }
    if ($ModelDir) { $arguments += @('--model-dir', $ModelDir) }
    if ($bootstrapped) { $arguments += '--python-installed' }
    & $selected @arguments
    exit $LASTEXITCODE
} catch {
    @{ ok=$false; status='failed'; error=$_.Exception.Message; message='初始化未完成；保留已有环境和下载缓存，未宣称依赖齐全。' } | ConvertTo-Json -Compress
    exit 1
}

