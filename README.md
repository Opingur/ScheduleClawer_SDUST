# 山科课表导出器

> 面向山东科技大学教务系统的 Windows 本地工具。它通过 WebVPN 登录教务系统，读取“学期理论课表”的全部周次，并生成带实际日期、上课时间、地点、教师和课程颜色的 Excel 课表。

![Platform](https://img.shields.io/badge/platform-Windows%20x64-0078D4)
![Release](https://img.shields.io/github/v/release/Opingur/ScheduleClawer_SDUST?display_name=tag)

当前稳定版本：[v1.0.2](https://github.com/Opingur/ScheduleClawer_SDUST/releases/tag/v1.0.2)。请从 Release 下载 [ScheduleExporter_SDUST_Installer_v1.0.2.exe](https://github.com/Opingur/ScheduleClawer_SDUST/releases/download/v1.0.2/ScheduleExporter_SDUST_Installer_v1.0.2.exe)。

## 网页版（无需安装）

可直接打开 [山科课表导出器网页版](https://opingur.github.io/ScheduleClawer_SDUST/)；它适合无法运行 Windows 安装版的用户。

网页版不会要求或保存 WebVPN、教务系统账号和密码。用户需要先自行登录并在“学期理论课表”中选择“全部”查询，再将页面提供的“导出山科课表”按钮拖入浏览器收藏栏，在课表页点击收藏生成本地 Excel。它主要支持 Chrome、Edge、Firefox、Safari 等桌面浏览器。Firefox 用户可显示“书签工具栏”后拖入按钮，或复制按钮代码新建收藏。

受浏览器安全机制限制，纯静态网页不能替用户自动登录，也可能受学校页面的 CSP 或跨域 iframe 限制而无法读取课表；此时没有网页端的自动绕过方式，可改用桌面版或反馈脱敏截图。
## 适用范围

- 仅适配山东科技大学当前的 WebVPN 与教务系统页面；
- 仅支持 Windows x64；
- 需要有效的学号、WebVPN 密码，以及教务系统密码；
- 程序使用同一个学号登录两个系统；若两个系统密码不同，可以分别填写；
- 需要网络能够访问 `webvpn.sdust.edu.cn`。

学校页面改版、临时启用验证码、强制改密、账号锁定或网络异常，都可能使自动化流程停在浏览器里。这不是对其他学校教务系统的通用爬虫，也与山东科技大学及其教务系统没有官方隶属关系。

## 安装

1. 在 [Releases](https://github.com/Opingur/ScheduleClawer_SDUST/releases) 下载最新的 `ScheduleExporter_SDUST_Installer_*.exe`。
2. 双击安装程序，选择安装位置；按需勾选“创建桌面快捷方式”。
3. 从开始菜单或桌面快捷方式启动“课表导出器”。不要只复制安装目录中的单个 EXE 到别处运行。

安装版已内置 Chromium 浏览器和 Excel 导出组件，不需要额外安装 Python、Node.js 或 Playwright。安装包没有代码签名时，Windows 可能显示 SmartScreen 提示；请只从本仓库的 Release 下载，并核对发布版本后再继续。程序目前没有自动更新功能。

## 首次导出

1. 填写学号和 WebVPN 密码。
2. 默认勾选“两个系统使用同一密码”。若教务系统密码不同，取消勾选后填写“教务系统密码”。
3. 填写学期总周数（1–30）和学校校历中的“第 1 周周一”。日期必须是 `YYYY-MM-DD`，且必须是周一。
4. 选择 Excel 保存位置；默认文件名为 `我的课表.xlsx`。建议按学期或日期改名，避免同名文件被覆盖。
5. 点击“自动登录并导出 Excel”，保持程序和自动打开的浏览器运行。
6. 成功后点击“打开输出文件夹”查看工作簿。

程序会依次完成 WebVPN 登录、教务系统登录、处理“进入首页”中转页，随后进入“培养服务 → 我的课表 → 学期理论课表”，将周次设为“全部”并查询。窗口中的状态文字和进度条会显示当前阶段。

若出现验证码、强制改密或页面提示，程序会保留浏览器现场供检查，不会自动关闭。处理问题后，请回到程序重新点击导出；保留现场用于排查，并不表示可从中断处继续运行。

## Excel 内容

导出的工作簿包含三类工作表：

- `20周总览`：按周汇总当天课程的紧凑列表。该工作表名称固定，即使你把总周数改为其他数字也不会改名。
- `第1周` 至 `第N周`：每周一张可打印的网格课表。星期标题正上方为根据“第 1 周周一”推算的实际日期。
- `课程明细`：便于筛选、检索的课程记录表。

每张周课表会显示课程名、时间、节次、地点和教师。颜色按课程名稳定分配，仅用于视觉区分，不表示必修、选修等课程类别。跨多个连续时段的课程会纵向合并，例如第 5–8 节会占用相应的多个时间格。

日期仅根据你填写的第 1 周周一顺推；程序不会自动识别节假日、调休、停课或校历变更。周课表只显示该周出现过课程的标准时间段，完全空闲的时间段不会单独生成一行。

## 登录信息与本地数据

密码只用于本机的浏览器自动填写，不会写入 Excel、运行日志或调试快照。

如果勾选“验证成功后加密保存在本机”，成功完成两层登录后，学号和两套密码会使用 Windows DPAPI 加密保存到：

```text
%LOCALAPPDATA%\课表导出器\credentials.dat
```

只有当前 Windows 用户可以解密。它不是跨设备同步的密码管理器；能以当前 Windows 用户身份运行的程序仍应被视为同一安全边界。不想保存时请取消勾选；已保存的信息可在程序中点击“清除本机凭据”清空。

默认导出文件和排错快照位于：

```text
%LOCALAPPDATA%\课表导出器\exports\
```

其中 `last_read_debug.json` 不含密码，但可能包含课程、教师、地点、课表页面地址和页面诊断信息。请不要将它、`credentials.dat`、浏览器 Cookie、含个人课表的 Excel 或任何密码公开发布。反馈问题时请先脱敏，并通过私密渠道发送必要的截图或日志。

## 常见问题

| 现象 | 处理方式 |
| --- | --- |
| 提示找不到 Chromium / `chrome.exe` | 请卸载旧版后从 Release 重新安装最新版安装包。v1.0.2 已将浏览器内核随应用打包。不要使用仅复制出来的 EXE。 |
| WebVPN 或教务系统登录失败 | 核对学号和密码；如果两个系统密码不同，取消“两个系统使用同一密码”后分别填写。确认网络可以打开 WebVPN。 |
| 浏览器显示验证码、改密页面或其他提示 | 在保留的浏览器页面处理或记录问题；随后回到程序重新点击导出。 |
| 提示未识别到课程卡片 | 确认系统中课表已查询且周次为“全部”。也可能是学校页面结构已变更；请提供脱敏截图和版本号反馈。 |
| 提示“第 1 周日期需要填写周一” | 将日期改为学校校历中的第 1 周周一，格式如 `2026-08-31`。 |
| 点击“打开输出文件夹”无效 | 该按钮仅在一次导出成功后可用；也可按保存位置在资源管理器中直接打开文件。 |

## 开发运行

开发环境需要 Windows、Python 3.10+ 和网络访问权限。在仓库根目录执行：

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python app.py
```

源代码运行时的 Playwright 浏览器需单独安装，因此不能把“已安装 Python 包”误认为“浏览器已下载”。普通使用者应优先使用 Release 的安装版。

### 项目结构

```text
app.py                    程序入口
src/desktop_app.py        Tkinter 界面、进度与交互
src/browser_reader.py     可见 Chromium 自动登录与课表读取
src/normalize.py          课表卡片解析、周次与时段标准化
src/export_xlsx.py        Excel 布局、着色与长课合并
src/export_service.py     导出编排与本地目录
src/credential_store.py   Windows DPAPI 凭据存取
build_release.ps1         应用和安装包构建脚本
installer.iss             Inno Setup 安装器配置
```

数据流为：`desktop_app → browser_reader → normalize → export_xlsx`。

## 构建安装包

在仓库根目录准备 Python、Inno Setup 6 和 PyInstaller。`PyInstaller` 是构建依赖，不在运行依赖文件中，需要额外安装：

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller
.\build_release.ps1
```

构建脚本会下载 Playwright Chromium，并输出：

- `release\app\课表导出器\课表导出器.exe`：独立应用目录；
- `release\课表导出器安装程序.exe`：可分发的安装程序。

发布前建议至少手工验证：安装版可在未安装 Python 的 Windows 用户环境启动；同密码和不同密码两种登录；示例导出；实际日期计算；跨时段长课的纵向合并；“清除本机凭据”；以及“打开输出文件夹”。

仓库已忽略凭据、浏览器状态、导出文件和构建产物。提交或发布前仍应检查 `git status`，避免上传任何本地个人数据。

## 近期更新

- `v1.0.2`：安装版显式使用随应用打包的 Chromium，修复他人电脑上找不到 Playwright 浏览器的问题。
- `v1.0.1`：修复跨多个连续时段的长课未占满对应时间格的问题。