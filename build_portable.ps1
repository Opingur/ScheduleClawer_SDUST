param(
    [string]$Python = "python",
    [string]$OutputName = "山科课表导出器_免安装包_v1.0.3"
)

$ErrorActionPreference = "Stop"
$env:PLAYWRIGHT_BROWSERS_PATH = "0"

$projectRoot = (Get-Location).Path
$releaseRoot = Join-Path $projectRoot ("release\" + $OutputName)
$sourceData = Join-Path $projectRoot "src"
$playwrightPackagePath = Split-Path (& $Python -c "import playwright; print(playwright.__file__)" -Raw).Trim()
$browserData = Join-Path $playwrightPackagePath "driver\package\.local-browsers"

if (Test-Path -LiteralPath $releaseRoot) {
    throw "目标目录已存在，为避免覆盖现有发布包，未继续构建：$releaseRoot"
}

if (-not (Test-Path -LiteralPath $browserData)) {
    & $Python -m playwright install chromium
    if ($LASTEXITCODE) { throw "Chromium 下载失败。" }
}

& $Python -m PyInstaller --noconfirm --windowed --name "课表导出器" `
    --distpath $releaseRoot `
    --workpath "build\portable-work" `
    --specpath "build\portable-spec" `
    --add-data "${sourceData};src" `
    --collect-all playwright `
    (Join-Path $projectRoot "app.py")
if ($LASTEXITCODE) { throw "便携版构建失败。" }

# PyInstaller 可能忽略以“.”开头的 .local-browsers 目录，因此在构建后显式复制。
$playwrightPackage = Join-Path $releaseRoot "课表导出器\_internal\playwright\driver\package"
New-Item -ItemType Directory -Force -Path $playwrightPackage | Out-Null
Copy-Item -LiteralPath $browserData -Destination $playwrightPackage -Recurse -Force

$bundledChrome = Get-ChildItem -LiteralPath (Join-Path $playwrightPackage ".local-browsers") -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "chrome.exe" -and $_.FullName.Contains("\chromium-") -and $_.FullName.Contains("\chrome-win") } |
    Select-Object -First 1
if (-not $bundledChrome) {
    throw "Chromium 没有被复制到便携包；为避免发布不可用文件，构建已停止。"
}

Copy-Item -LiteralPath (Join-Path $projectRoot "web\启动课表导出器网页版.html") -Destination (Join-Path $releaseRoot "网页版启动器.html")
@"
山科课表导出器免安装包

1. 网页版：双击“网页版启动器.html”。它会使用默认浏览器打开网页；在同一个浏览器中登录 WebVPN 和教务系统，然后按网页提示导出。
2. Windows 便携版：双击“课表导出器\课表导出器.exe”。无需安装，内置 Chromium 浏览器内核。
3. 不要只复制 EXE 文件；必须保留整个“课表导出器”文件夹，否则内置浏览器无法运行。
4. 程序未签名时 Windows 可能显示 SmartScreen 提示，请只从项目官方发布包获取文件。
"@ | Set-Content -LiteralPath (Join-Path $releaseRoot "使用说明.txt") -Encoding utf8

Write-Host "免安装发布包：$releaseRoot"
Write-Host "内置 Chromium：$($bundledChrome.FullName)"
