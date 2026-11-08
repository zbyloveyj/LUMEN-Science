$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $taskRoot '.tools'
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
$nsisDir = Join-Path $toolsDir 'nsis-3.11'
if (-not (Test-Path -LiteralPath (Join-Path $nsisDir 'makensis.exe'))) {
    $archive = Join-Path $toolsDir 'nsis-3.11.zip'
    Invoke-WebRequest 'https://netix.dl.sourceforge.net/project/nsis/NSIS%203/3.11/nsis-3.11.zip' -OutFile $archive
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne 'C7D27F780DDB6CFFB4730138CD1591E841F4B7EDB155856901CDF5F214394FA1') {
        throw 'NSIS archive checksum mismatch.'
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $toolsDir -Force
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
