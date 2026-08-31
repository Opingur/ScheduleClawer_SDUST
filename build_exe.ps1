param(
    [string]$Python = "python"
)

# 兼容旧命令：现在统一构建独立应用目录和安装程序。
& "$PSScriptRoot\build_release.ps1" -Python $Python
exit $LASTEXITCODE