param(
    [string]$Python = "python"
)

# 保留旧脚本名以兼容现有构建命令；默认只生成免安装便携包。
& "$PSScriptRoot\build_portable.ps1" -Python $Python
exit $LASTEXITCODE
