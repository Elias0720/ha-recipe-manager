[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$componentRoot = Join-Path $root "custom_components\ha_recipe_manager"
$manifestPath = Join-Path $componentRoot "manifest.json"
$appConfigPath = Join-Path $root "get_ha_recipe_manager\config.yaml"
$distDirectory = Join-Path $root "dist"
$distArchive = Join-Path $distDirectory "ha_recipe_manager.zip"
$appArchive = Join-Path $root "get_ha_recipe_manager\ha_recipe_manager.zip"
$checksumPath = Join-Path $root "get_ha_recipe_manager\ha_recipe_manager.zip.sha256"

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$appVersionMatch = Select-String -LiteralPath $appConfigPath -Pattern '^version:\s*"?([^"\s]+)"?\s*$'

if (-not $appVersionMatch) {
    throw "In get_ha_recipe_manager/config.yaml wurde keine Version gefunden."
}

$appVersion = $appVersionMatch.Matches[0].Groups[1].Value
if ($manifest.version -ne $appVersion) {
    throw "Die Integrationsversion $($manifest.version) stimmt nicht mit der App-Version $appVersion ueberein."
}

$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$stagingRoot = Join-Path $tempBase ("ha-recipe-manager-" + [guid]::NewGuid().ToString("N"))
$stagingRoot = [System.IO.Path]::GetFullPath($stagingRoot)

if (-not $stagingRoot.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Das temporaere Arbeitsverzeichnis liegt ausserhalb des Temp-Verzeichnisses."
}

try {
    $stagingComponent = Join-Path $stagingRoot "custom_components\ha_recipe_manager"
    New-Item -ItemType Directory -Path $stagingComponent -Force | Out-Null

    Get-ChildItem -LiteralPath $componentRoot -Recurse -File |
        Where-Object { $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc' } |
        ForEach-Object {
            $relativePath = $_.FullName.Substring($componentRoot.Length).TrimStart('\', '/')
            $destination = Join-Path $stagingComponent $relativePath
            New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
        }

    New-Item -ItemType Directory -Path $distDirectory -Force | Out-Null
    if (Test-Path -LiteralPath $distArchive) {
        Remove-Item -LiteralPath $distArchive -Force
    }

    Compress-Archive -Path (Join-Path $stagingRoot "custom_components") -DestinationPath $distArchive -CompressionLevel Optimal
    Copy-Item -LiteralPath $distArchive -Destination $appArchive -Force

    $hash = (Get-FileHash -LiteralPath $appArchive -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath $checksumPath -Value "$hash  ha_recipe_manager.zip" -Encoding ascii

    Write-Host "Release-Paket erstellt: $distArchive"
    Write-Host "Installer-Paket aktualisiert: $appArchive"
    Write-Host "SHA-256: $hash"
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
