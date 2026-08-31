param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$env:PLAYWRIGHT_BROWSERS_PATH = "0"
$ProjectRoot = (Get-Location).Path
$SourceData = Join-Path $ProjectRoot "src"
$BrowserData = Join-Path (Split-Path (& $Python -c "import playwright; print(playwright.__file__)" -Raw).Trim()) "driver\package\.local-browsers"

& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE) { throw "依赖安装失败。" }
& $Python -m playwright install chromium
if ($LASTEXITCODE) { throw "Chromium 安装失败。" }

& $Python -m PyInstaller --noconfirm --windowed --name "课表导出器" `
    --distpath "release\app" `
    --workpath "build\release-work" `
    --specpath "build\release-spec" `
    --add-data "${SourceData};src" `
    --add-data "${BrowserData};playwright\driver\package\.local-browsers" `
    --collect-all playwright `
    (Join-Path $ProjectRoot "app.py")
if ($LASTEXITCODE) { throw "PyInstaller 构建失败。" }

$compiler = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $compiler) {
    throw "未找到 Inno Setup 6。请安装后重新运行本脚本。"
}
& $compiler "/Q" (Join-Path $ProjectRoot "installer.iss")
if ($LASTEXITCODE) { throw "安装程序编译失败。" }

Write-Host "应用目录：release\app\课表导出器"
Write-Host "安装程序：release\课表导出器安装程序.exe"