# 山科课表导出器

> 面向**山东科技大学**教务系统的本地课表导出工具。它会通过 WebVPN 登录教务系统，读取“学期理论课表”的全部周次，并生成按周展开、带实际日期和课程颜色的 Excel 课表。

![Platform](https://img.shields.io/badge/platform-Windows-0078D4)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)

## 给普通使用者

前往仓库的 **Releases** 下载 `课表导出器安装程序.exe`，双击安装即可：

- 安装位置可以自行选择；
- 安装向导默认提供“创建桌面快捷方式”；
- 运行后在程序窗口填写学号和密码，点击“自动登录并导出 Excel”；
- 安装包已内置浏览器内核和 Excel 导出组件，**不需要安装 Python、Node.js 或 Playwright**。

安装包体积较大，是因为包含了可独立运行的 Chromium 浏览器。

## 功能

- 自动完成 WebVPN 与教务系统两层登录；
- 自动处理教务系统的“进入首页”中转页；
- 自动进入“培养服务 → 我的课表 → 学期理论课表”，选择“全部”并查询；
- 生成 `20周总览`、每周课表和`课程明细`三个层次的 Excel；
- 每个每周课表会在星期标题上方标出实际日期；
- 按课程名称着色，并保留上课钟点、节次、地点与教师；
- 显示导出进度，成功后可一键打开输出文件夹；
- 可使用 Windows DPAPI 加密保存本机凭据，仅当前 Windows 用户可以解密。

## 使用提醒

- 本项目仅适配山东科技大学当前的 WebVPN 与教务系统页面结构，学校页面改版后可能需要更新选择器。
- 密码仅用于本机浏览器自动填写；启用“保存本机凭据”后，会通过 Windows DPAPI 加密，不会写入 Excel、日志或调试课表数据。
- 如学校临时要求验证码、强制修改密码或出现页面提示，程序会保留浏览器现场，方便处理后重新导出。
- 本项目与山东科技大学及其教务系统没有官方隶属关系。

## 开发运行

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python app.py
```

## 构建发布版

在 Windows 开发环境中安装 Python、Playwright Chromium 和 Inno Setup 6 后运行：

```powershell
.\build_release.ps1
```

将生成：

- `release\app\课表导出器\课表导出器.exe`：独立应用目录；
- `release\课表导出器安装程序.exe`：可分发的安装程序。

## 技术说明

- 图形界面：Tkinter；
- 网页自动化：Playwright Chromium；
- Excel：openpyxl；
- 安装包：Inno Setup。