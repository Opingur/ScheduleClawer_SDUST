from __future__ import annotations

import os
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.browser_reader import BrowserSession, extract_from_open_page, save_debug_snapshot
from src.credential_store import CredentialStore
from src.export_service import EXPORT_DIR, PROFILE_DIR, USER_ROOT, load_demo_payload, run_exporter
from src.normalize import normalise_cards


DEFAULT_TERM_START = "2026-08-31"


class ScheduleDesktopApp:
    """原生 Tkinter 外壳；浏览器只承担可见的自动登录与读取工作。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("课表导出器")
        self.root.minsize(720, 620)
        self.root.geometry("820x700")

        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="schedule-export")
        self.session: BrowserSession | None = None
        self.busy = False
        self.store = CredentialStore(USER_ROOT / "credentials.dat")

        self.username_var = tk.StringVar()
        self.vpn_password_var = tk.StringVar()
        self.academic_password_var = tk.StringVar()
        self.same_password_var = tk.BooleanVar(value=True)
        self.remember_var = tk.BooleanVar(value=True)
        self.use_saved_var = tk.BooleanVar(value=False)
        self.week_count_var = tk.IntVar(value=20)
        self.term_start_var = tk.StringVar(value=DEFAULT_TERM_START)
        self.output_var = tk.StringVar(value=str(EXPORT_DIR / "我的课表.xlsx"))
        self.status_var = tk.StringVar(value="准备就绪。首次使用请填写学号和密码。")
        self.saved_hint_var = tk.StringVar()
        self.progress_var = tk.IntVar(value=0)
        self.last_output_dir: Path | None = None

        self._build()
        self._refresh_saved_hint()
        self.root.after(120, self._drain_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)

        ttk.Label(outer, text="课表导出器", font=("Microsoft YaHei UI", 20, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            outer,
            text="自动登录 WebVPN 与教务系统，读取“全部周次”课表并生成彩色 Excel。",
            foreground="#666666",
        ).grid(row=1, column=0, sticky="w", pady=(4, 14))

        account_box = ttk.LabelFrame(outer, text="登录信息", padding=12)
        account_box.grid(row=2, column=0, sticky="ew")
        account_box.columnconfigure(1, weight=1)

        ttk.Label(account_box, text="学号：").grid(row=0, column=0, sticky="w", pady=4)
        self.username_entry = ttk.Entry(account_box, textvariable=self.username_var, width=42)
        self.username_entry.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(account_box, text="WebVPN 密码：").grid(row=1, column=0, sticky="w", pady=4)
        self.vpn_entry = ttk.Entry(account_box, textvariable=self.vpn_password_var, show="●", width=42)
        self.vpn_entry.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(account_box, text="教务系统密码：").grid(row=2, column=0, sticky="w", pady=4)
        self.academic_entry = ttk.Entry(
            account_box, textvariable=self.academic_password_var, show="●", width=42
        )
        self.academic_entry.grid(row=2, column=1, sticky="ew", pady=4)

        self.same_check = ttk.Checkbutton(
            account_box,
            text="两个系统使用同一密码",
            variable=self.same_password_var,
            command=self._sync_password_mode,
        )
        self.same_check.grid(row=3, column=1, sticky="w", pady=(6, 0))
        ttk.Checkbutton(
            account_box,
            text="验证成功后加密保存在本机（仅当前 Windows 用户可解密）",
            variable=self.remember_var,
        ).grid(row=4, column=1, sticky="w", pady=(2, 0))
        ttk.Checkbutton(
            account_box,
            text="使用已保存的登录信息",
            variable=self.use_saved_var,
            command=self._sync_saved_mode,
        ).grid(row=5, column=1, sticky="w", pady=(2, 0))

        saved_line = ttk.Frame(account_box)
        saved_line.grid(row=6, column=1, sticky="w", pady=(5, 0))
        ttk.Label(saved_line, textvariable=self.saved_hint_var, foreground="#666666").pack(side="left")
        self.clear_button = ttk.Button(saved_line, text="清除本机凭据", command=self._clear_saved)
        self.clear_button.pack(side="left", padx=(10, 0))

        export_box = ttk.LabelFrame(outer, text="导出设置", padding=12)
        export_box.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        export_box.columnconfigure(1, weight=1)
        ttk.Label(export_box, text="学期总周数：").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Spinbox(export_box, from_=1, to=30, textvariable=self.week_count_var, width=8).grid(
            row=0, column=1, sticky="w", pady=4
        )
        ttk.Label(export_box, text="第 1 周周一：").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(export_box, textvariable=self.term_start_var, width=16).grid(
            row=1, column=1, sticky="w", pady=4
        )
        ttk.Label(export_box, text="格式：YYYY-MM-DD", foreground="#666666").grid(
            row=1, column=1, sticky="w", padx=(150, 0)
        )
        ttk.Label(export_box, text="保存位置：").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(export_box, textvariable=self.output_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Button(export_box, text="选择…", command=self._choose_output).grid(
            row=2, column=2, padx=(8, 0), pady=4
        )

        action_box = ttk.LabelFrame(outer, text="操作", padding=12)
        action_box.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(
            action_box,
            text=(
                "点击后会打开一个可见浏览器，并自动填写两层登录；教务系统的“进入首页”中转页也会自动处理。\n"
                "若学校出现验证码、强制改密或页面改版，浏览器会保留在现场，程序不会关闭。"
            ),
            justify="left",
            foreground="#555555",
        ).pack(anchor="w")
        controls = ttk.Frame(action_box)
        controls.pack(anchor="w", pady=(10, 0))
        self.export_button = ttk.Button(
            controls, text="自动登录并导出 Excel", command=self._start_export
        )
        self.export_button.pack(side="left")
        self.demo_button = ttk.Button(controls, text="生成示例 Excel", command=self._start_demo)
        self.demo_button.pack(side="left", padx=(10, 0))
        self.open_folder_button = ttk.Button(
            controls, text="打开输出文件夹", command=self._open_output_folder
        )
        self.open_folder_button.pack(side="left", padx=(10, 0))
        self.open_folder_button.state(["disabled"])

        status_box = ttk.LabelFrame(outer, text="状态", padding=12)
        status_box.grid(row=5, column=0, sticky="nsew", pady=(12, 0))
        outer.rowconfigure(5, weight=1)
        ttk.Label(status_box, textvariable=self.status_var, justify="left", wraplength=740).pack(
            anchor="w", fill="x"
        )
        self.progress_bar = ttk.Progressbar(
            status_box, maximum=100, mode="determinate", variable=self.progress_var
        )
        self.progress_bar.pack(anchor="w", fill="x", pady=(9, 0))

        self._sync_password_mode()

    def _sync_password_mode(self) -> None:
        if self.same_password_var.get():
            self.academic_password_var.set("")
            self.academic_entry.state(["disabled"])
        else:
            self.academic_entry.state(["!disabled"])

    def _sync_saved_mode(self) -> None:
        saved_mode = self.use_saved_var.get()
        state = ["disabled"] if saved_mode else ["!disabled"]
        for widget in (self.username_entry, self.vpn_entry, self.academic_entry, self.same_check):
            widget.state(state)
        if not saved_mode:
            self._sync_password_mode()

    def _refresh_saved_hint(self) -> None:
        try:
            meta = self.store.metadata()
        except RuntimeError:
            meta = {"saved": False, "maskedUsername": ""}
        if meta["saved"]:
            self.saved_hint_var.set(f"已保存账号：{meta['maskedUsername']}（Windows DPAPI 加密）")
            self.clear_button.state(["!disabled"])
        else:
            self.saved_hint_var.set("当前没有可用的本机凭据")
            self.clear_button.state(["disabled"])
            self.use_saved_var.set(False)

    def _clear_saved(self) -> None:
        if not messagebox.askyesno("清除本机凭据", "将覆盖本机保存的加密登录信息，是否继续？", parent=self.root):
            return
        try:
            self.store.clear()
        except Exception as error:
            messagebox.showerror("清除失败", str(error), parent=self.root)
            return
        self._refresh_saved_hint()
        self.status_var.set("本机加密凭据已清除。")

    def _choose_output(self) -> None:
        chosen = filedialog.asksaveasfilename(
            title="保存课表 Excel",
            initialfile=Path(self.output_var.get() or "我的课表.xlsx").name,
            defaultextension=".xlsx",
            filetypes=[("Excel 工作簿", "*.xlsx")],
            parent=self.root,
        )
        if chosen:
            self.output_var.set(chosen)

    def _open_output_folder(self) -> None:
        folder = self.last_output_dir
        if not folder or not folder.is_dir():
            messagebox.showwarning("尚无导出文件", "请先成功导出一份课表。", parent=self.root)
            return
        try:
            os.startfile(str(folder))
        except OSError as error:
            messagebox.showerror("无法打开文件夹", str(error), parent=self.root)

    @staticmethod
    def _progress_value(message: str) -> int:
        milestones = (
            ("准备", 5),
            ("打开 WebVPN", 15),
            ("登录 WebVPN", 30),
            ("登录教务系统", 48),
            ("中转页", 58),
            ("进入教务首页", 60),
            ("周次设为", 68),
            ("读取课表", 78),
            ("生成 Excel", 94),
            ("已读取", 86),
        )
        return next((value for marker, value in milestones if marker in message), 8)

    def _payload_from_form(self) -> dict:
        try:
            first_monday = date.fromisoformat(self.term_start_var.get().strip())
        except ValueError as error:
            raise ValueError("第 1 周周一日期格式应为 YYYY-MM-DD。") from error
        if first_monday.weekday() != 0:
            raise ValueError("第 1 周日期需要填写周一。")
        output = Path(self.output_var.get().strip()).expanduser()
        if not output.name:
            raise ValueError("请填写 Excel 保存位置。")
        if output.suffix.lower() != ".xlsx":
            output = output.with_suffix(".xlsx")
        return {
            "week_count": int(self.week_count_var.get()),
            "term_start_monday": first_monday.isoformat(),
            "output": output,
            "use_saved": self.use_saved_var.get(),
            "remember": self.remember_var.get(),
            "username": self.username_var.get().strip(),
            "vpn_password": self.vpn_password_var.get(),
            "academic_password": self.vpn_password_var.get()
            if self.same_password_var.get()
            else self.academic_password_var.get(),
        }

    def _start_export(self) -> None:
        if self.busy:
            return
        try:
            payload = self._payload_from_form()
            if not payload["use_saved"] and (
                not payload["username"] or not payload["vpn_password"] or not payload["academic_password"]
            ):
                raise ValueError("请填写学号、WebVPN 密码和教务系统密码，或勾选“使用已保存的登录信息”。")
            if payload["use_saved"] and not self.store.metadata().get("saved"):
                raise ValueError("没有可用的本机凭据，请取消勾选后重新填写。")
        except (ValueError, RuntimeError) as error:
            messagebox.showwarning("无法开始", str(error), parent=self.root)
            return
        self._set_busy(True, "正在准备浏览器自动登录…")
        self.executor.submit(self._export_worker, payload)

    def _start_demo(self) -> None:
        if self.busy:
            return
        try:
            payload = self._payload_from_form()
        except ValueError as error:
            messagebox.showwarning("无法开始", str(error), parent=self.root)
            return
        self._set_busy(True, "正在生成示例 Excel…")
        self.executor.submit(self._demo_worker, payload)

    def _progress(self, message: str) -> None:
        self.events.put(("progress", message))

    def _close_session_in_worker(self) -> None:
        if self.session:
            try:
                self.session.close()
            finally:
                self.session = None

    def _credentials_for(self, payload: dict) -> tuple[str, str, str]:
        if payload["use_saved"]:
            saved = self.store.load()
            if not saved:
                raise RuntimeError("没有读取到可用的本机凭据，请重新填写。")
            return saved["username"], saved["vpnPassword"], saved["academicPassword"]
        return payload["username"], payload["vpn_password"], payload["academic_password"]

    def _export_worker(self, payload: dict) -> None:
        try:
            self._close_session_in_worker()
            username, vpn_password, academic_password = self._credentials_for(payload)
            self.session = BrowserSession(PROFILE_DIR)
            page = self.session.login_and_open_timetable(
                username, vpn_password, academic_password, on_status=self._progress
            )
            # 两层登录与课表页面均已确认可用后即保存，不受后续导出故障影响。
            if payload["remember"] and not payload["use_saved"]:
                self.store.save(username, vpn_password, academic_password)
            self._progress("正在读取课表卡片…")
            raw = extract_from_open_page(page)
            debug_path = EXPORT_DIR / "last_read_debug.json"
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            save_debug_snapshot(raw, debug_path)
            courses = normalise_cards(raw["cards"], raw["timeMap"], payload["week_count"])
            if not courses:
                raise RuntimeError("已打开课表，但没有识别到课程卡片；真实浏览器已保留以便检查。")
            self._progress(f"已读取 {len(courses)} 条周次课程记录，正在生成 Excel…")
            run_exporter(
                {
                    "weekCount": payload["week_count"],
                    "termStartMonday": payload["term_start_monday"],
                    "courses": courses,
                    "timeMap": raw["timeMap"],
                },
                payload["output"],
            )
            self._close_session_in_worker()
            self.events.put(("success", (payload["output"], len(courses))))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _demo_worker(self, payload: dict) -> None:
        try:
            demo = load_demo_payload()
            demo["weekCount"] = payload["week_count"]
            demo["termStartMonday"] = payload["term_start_monday"]
            run_exporter(demo, payload["output"])
            self.events.put(("success", (payload["output"], len(demo.get("courses", [])))))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _set_busy(self, busy: bool, status: str | None = None) -> None:
        self.busy = busy
        controls = [self.export_button, self.demo_button, self.clear_button]
        for control in controls:
            control.state(["disabled"] if busy else ["!disabled"])
        if busy:
            self.open_folder_button.state(["disabled"])
            self.progress_var.set(5)
        elif self.last_output_dir and self.last_output_dir.is_dir():
            self.open_folder_button.state(["!disabled"])
        if status:
            self.status_var.set(status)

    def _drain_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    message = str(value)
                    self.status_var.set(message)
                    self.progress_var.set(max(self.progress_var.get(), self._progress_value(message)))
                elif kind == "success":
                    output, count = value
                    self.last_output_dir = Path(output).parent
                    self.progress_var.set(100)
                    self._set_busy(False, f"导出完成：{output}")
                    self._refresh_saved_hint()
                    messagebox.showinfo(
                        "导出完成",
                        f"已生成 Excel：\n{output}\n\n共写入 {count} 条周次课程记录。",
                        parent=self.root,
                    )
                elif kind == "error":
                    self._set_busy(False, "自动导出未完成；真实浏览器已保留，可检查学校页面提示。")
                    messagebox.showerror(
                        "操作未完成",
                        f"{value}\n\n浏览器没有被关闭。处理完验证码、密码或页面提示后，可回到本程序再次点击导出。",
                        parent=self.root,
                    )
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(120, self._drain_events)

    def _on_close(self) -> None:
        if self.busy:
            messagebox.showinfo("任务进行中", "当前正在读取或导出，请等待完成后再关闭窗口。", parent=self.root)
            return
        self.executor.submit(self._close_session_in_worker)
        self.executor.shutdown(wait=False, cancel_futures=False)
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style(root).theme_use("vista")
    except tk.TclError:
        pass
    ScheduleDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()