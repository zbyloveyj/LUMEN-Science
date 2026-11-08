param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $taskRoot '.tools'
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
$nsisDir = Join-Path $toolsDir 'nsis-3.11'
if (-not (Test-Path -LiteralPath (Join-Path $nsisDir 'makensis.exe'))) {
    & $Python (Join-Path $PSScriptRoot 'fetch_nsis.py')
    if ($LASTEXITCODE -ne 0) { throw 'Verified NSIS download failed.' }
}
$bootstrap = Join-Path $toolsDir 'MicrosoftEdgeWebview2Setup.exe'
if (-not (Test-Path -LiteralPath $bootstrap)) {
    Invoke-WebRequest 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $bootstrap
}
$signature = Get-AuthenticodeSignature -LiteralPath $bootstrap
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') {
    throw 'The Microsoft WebView2 bootstrapper signature could not be verified.'
}
Write-Output (Join-Path $nsisDir 'makensis.exe')
