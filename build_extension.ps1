param(
    [string]$OutputName = "浏览器插件测试版"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression.FileSystem

$projectRoot = (Get-Location).Path
$sourceRoot = Join-Path $projectRoot "extension"
$outputRoot = Join-Path $projectRoot $OutputName
$zipPath = Join-Path $projectRoot ("$OutputName.zip")

if (Test-Path -LiteralPath $outputRoot) {
    throw "目标目录已存在，为避免覆盖现有测试包，未继续构建：$outputRoot"
}
if (Test-Path -LiteralPath $zipPath) {
    throw "目标压缩包已存在，为避免覆盖现有测试包，未继续构建：$zipPath"
}

New-Item -ItemType Directory -Path $outputRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceRoot "manifest.json") -Destination $outputRoot
Copy-Item -LiteralPath (Join-Path $sourceRoot "README.md") -Destination $outputRoot
Copy-Item -LiteralPath (Join-Path $sourceRoot "popup") -Destination (Join-Path $outputRoot "popup") -Recurse
Copy-Item -LiteralPath (Join-Path $sourceRoot "content") -Destination (Join-Path $outputRoot "content") -Recurse
Copy-Item -LiteralPath (Join-Path $sourceRoot "vendor") -Destination (Join-Path $outputRoot "vendor") -Recurse

$manifest = Get-Content -LiteralPath (Join-Path $outputRoot "manifest.json") -Raw | ConvertFrom-Json
if ($manifest.manifest_version -ne 3 -or -not (Test-Path -LiteralPath (Join-Path $outputRoot "content\exporter-core.js"))) {
    throw "测试包关键文件不完整。"
}

[System.IO.Compression.ZipFile]::CreateFromDirectory($outputRoot, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)
Write-Host "插件目录：$outputRoot"
Write-Host "插件压缩包：$zipPath"
