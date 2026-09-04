from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


WEBVPN_LOGIN_URL = "https://webvpn.sdust.edu.cn/login"
SCHEDULE_URL = "https://webvpn.sdust.edu.cn/http/77726476706e69737468656265737421fae046903f2426437a1d9ab8d6502720b230dc/jsxsd/"
TIMETABLE_URL = (
    SCHEDULE_URL
    + "xskb/xskb_list.do?viweType=0&showallprint=0&showkchprint=0"
    + "&showkink=0&showfzmprint=0&baseUrl=%2Fjsxsd&zc="
)


def _bundled_chromium_executable() -> Path | None:
    """返回 PyInstaller 安装目录中的 Chromium；开发运行时不干预默认路径。"""
    if not getattr(sys, "frozen", False):
        return None

    bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    browser_root = bundle_root / "playwright" / "driver" / "package" / ".local-browsers"
    candidates = sorted(browser_root.glob("chromium-*/chrome-win*/chrome.exe"))
    return candidates[0] if candidates else None

VPN_AUTH_STATE_SCRIPT = r"""
() => {
  const text = (document.body?.innerText || '').replace(/\s+/g, ' ');
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden'
      && rect.width > 0 && rect.height > 0;
  };
  const visiblePassword = Array.from(document.querySelectorAll('input[type="password"]'))
    .some(isVisible);
  const hasRecentVisits = text.includes('最近访问');
  const hasSchoolResources = text.includes('学校资源');
  const hasPortalTitle = text.includes('资源访问控制系统');
  const dashboard = hasRecentVisits && (hasSchoolResources || hasPortalTitle);
  return {
    authenticated: dashboard && !visiblePassword,
    dashboard,
    visiblePassword,
  };
}
"""


EXTRACT_PAGE_DATA = r"""
() => {
  const clean = (value) => (value || '').replace(/\u00a0/g, ' ').replace(/[ \t]+/g, ' ').trim();
  const hasCourseMeta = (value) => /(?:老师|教师)\s*[:：]/.test(value) && /时间\s*[:：]/.test(value);
  const hasUsableTitle = (value) => {
    const marker = value.search(/(?:老师|教师|时间|地点|教室)\s*[:：]/);
    if (marker <= 0) return false;
    return value.slice(0, marker).split(/\n+/).map(clean).filter(Boolean)
      .some((line) => !/^(?:课程编号|班级|总人数|考核方式|总学时|网课群号|网课链接|分组名)\s*[:：]/.test(line));
  };
  const cardTextFor = (element, leafText) => {
    let current = element;
    let best = leafText;
    while (current.parentElement && current.parentElement !== document.body) {
      const parent = current.parentElement;
      const metaLeaves = [...parent.querySelectorAll('*')]
        .filter((candidate) => hasCourseMeta(clean(candidate.innerText)))
        .filter((candidate) => ![...candidate.children].some((child) => hasCourseMeta(clean(child.innerText))));
      if (metaLeaves.length !== 1) break;
      const parentText = clean(parent.innerText);
      if (parentText.length <= 700 && hasUsableTitle(parentText)) best = parentText;
      current = parent;
      if (current.tagName === 'TD') break;
    }
    return best;
  };
  const headerFor = (cell) => {
    const table = cell.closest('table');
    if (!table) return '';
    const rows = [...table.querySelectorAll('tr')];
    const index = cell.cellIndex;
    const headerRow = rows.find((row) => /星期[一二三四五六日天]|周[一二三四五六日]/.test(row.innerText || ''));
    return headerRow && headerRow.cells[index] ? clean(headerRow.cells[index].innerText) : '';
  };
  const candidates = [...document.querySelectorAll('body *')]
    .map((element) => ({ element, text: clean(element.innerText) }))
    .filter(({ text }) => text.length >= 12 && text.length <= 700 && hasCourseMeta(text))
    .filter(({ element }) => ![...element.children].some((child) => hasCourseMeta(clean(child.innerText))))
    .map(({ element, text }) => {
      const cell = element.closest('td');
      return { text: cardTextFor(element, text), weekday: cell ? headerFor(cell) : '' };
    })
    .filter((item) => /星期[一二三四五六日天]|周[一二三四五六日]/.test(item.weekday));

  const uniqueCards = [...new Map(candidates.map((item) => [item.weekday + '|' + item.text, item])).values()];
  const timeMap = {};
  for (const row of [...document.querySelectorAll('tr')]) {
    const firstCell = row.cells && row.cells[0];
    if (!firstCell) continue;
    const label = clean(firstCell.innerText);
    const periods = label.match(/(\d{1,2})\s*[、,，]\s*(\d{1,2})\s*小节|第?\s*(\d{1,2})\s*(?:-|~|—|–)\s*(\d{1,2})\s*节/);
    const clock = label.match(/(\d{1,2}:\d{2})\s*(?:-|~|—|–)\s*(\d{1,2}:\d{2})/);
    if (!periods || !clock) continue;
    const start = Number(periods[1] || periods[3]);
    const end = Number(periods[2] || periods[4]);
    for (let period = Math.min(start, end); period <= Math.max(start, end); period += 1) {
      timeMap[String(period)] = { start: clock[1], end: clock[2] };
    }
  }
  return { title: document.title, cards: uniqueCards, timeMap, pageUrl: location.href };
}
"""


def _first_visible_locator(page, selectors):
    for frame in page.frames:
        for selector in selectors:
            try:
                matches = frame.locator(selector)
                for index in range(min(matches.count(), 8)):
                    candidate = matches.nth(index)
                    if candidate.is_visible():
                        return candidate
            except Exception:
                continue
    return None


def _visible_text(page) -> str:
    chunks = []
    for frame in page.frames:
        try:
            text = frame.locator("body").inner_text(timeout=1_000).strip()
        except Exception:
            continue
        if text:
            chunks.append(text)
    return " ".join(chunks)


def _login_error_hint(page) -> str:
    text = " ".join(_visible_text(page).split())
    keywords = ("错误", "失败", "不正确", "验证码", "锁定", "过期", "修改密码")
    for sentence in text.replace("！", "。").replace("!", "。").split("。"):
        if any(keyword in sentence for keyword in keywords):
            return sentence[:120]
    return ""


PASSWORD_SELECTORS = [
    'input[type="password"]',
    '#ppassword',
    'input[id*="password" i]',
    'input[name*="password" i]',
    'input[placeholder*="密码"]',
]


def _password_locator(page):
    return _first_visible_locator(page, PASSWORD_SELECTORS)


def _has_visible_password(page) -> bool:
    return _password_locator(page) is not None


ACADEMIC_USERNAME_SELECTORS = [
    'input[placeholder*="请输入账号"]',
    'input[placeholder*="账号"]',
    'input[placeholder*="学号"]',
    'input[autocomplete="username"]',
    'input[name="username"]',
    'input[name="USERNAME"]',
    '#username',
    'input[type="text"]',
]

ACADEMIC_PASSWORD_SELECTORS = [
    'input[type="password"]',
    'input[autocomplete="current-password"]',
    'input[placeholder*="密码"]',
    'input[aria-label*="密码"]',
    'input[id*="password" i]',
    'input[name*="password" i]',
    'input[id*="pwd" i]',
    'input[name*="pwd" i]',
]

ACADEMIC_SUBMIT_SELECTORS = [
    'button:has-text("立即登录")',
    'button:has-text("登 录")',
    'button:has-text("登录")',
    '[role="button"]:has-text("立即登录")',
    '[role="button"]:has-text("登录")',
    'a:has-text("立即登录")',
    'a:has-text("登录")',
    'input[type="submit"]',
    'input[value*="登录"]',
]


def _academic_login_controls(page):
    username = _first_visible_locator(page, ACADEMIC_USERNAME_SELECTORS)
    password = _first_visible_locator(page, ACADEMIC_PASSWORD_SELECTORS)
    submit = _first_visible_locator(page, ACADEMIC_SUBMIT_SELECTORS)
    if submit is None:
        for frame in page.frames:
            try:
                candidate = frame.get_by_text("立即登录", exact=True)
                for index in range(min(candidate.count(), 8)):
                    item = candidate.nth(index)
                    if item.is_visible():
                        submit = item
                        break
            except Exception:
                continue
            if submit is not None:
                break
    return username, password, submit


def _academic_form_diagnostic(page) -> str:
    """只记录控件结构，不读取或输出用户填入的密码。"""
    fields = []
    for frame in page.frames:
        try:
            inputs = frame.locator("input")
            for index in range(min(inputs.count(), 16)):
                item = inputs.nth(index)
                if not item.is_visible():
                    continue
                attrs = []
                for name in ("type", "id", "name", "placeholder", "autocomplete", "aria-label"):
                    value = item.get_attribute(name)
                    if value:
                        attrs.append(f"{name}={value}")
                fields.append("input(" + ", ".join(attrs) + ")")
        except Exception:
            continue
    return "；".join(fields) or "未发现可见 input"


def _click_text_in_frames(page, text: str) -> bool:
    """兼容学校页面中 a、button、div 等不同实现的可见文字控件。"""
    selectors = (
        f'a:has-text("{text}")',
        f'button:has-text("{text}")',
        f'[role="button"]:has-text("{text}")',
        f'[onclick]:has-text("{text}")',
    )
    for frame in page.frames:
        candidates = []
        try:
            candidates.append(frame.get_by_text(text, exact=True))
            candidates.append(frame.get_by_text(text, exact=False))
        except Exception:
            pass
        for selector in selectors:
            try:
                candidates.append(frame.locator(selector))
            except Exception:
                continue
        for matches in candidates:
            try:
                for index in range(min(matches.count(), 12)):
                    candidate = matches.nth(index)
                    if candidate.is_visible():
                        candidate.click(timeout=8_000, no_wait_after=True)
                        return True
            except Exception:
                continue
    return False


def _academic_home_url(page_url: str) -> str:
    """从 WebVPN 包装后的选课中转页推导同一会话下的学生首页。"""
    return (page_url or "").replace("xsrkxz.htmlx", "xsMain.html")


def _is_entry_choice_page(page) -> bool:
    """是否停在教务系统登录后的“进入首页”中转页。"""
    if any("xsrkxz.htmlx" in (frame.url or "").lower() for frame in page.frames):
        return True
    return "进入首页" in _visible_text(page)


def _enter_academic_home(page):
    """点击中转页的“进入首页”，并等待跳转完成（含新标签页）。"""
    if not _is_entry_choice_page(page):
        return page
    clicked = _click_text_in_frames(page, "进入首页")
    if not clicked:
        # 该中转页已在地址中明确给出，学校有时用脚本/非标准控件实现链接。
        # 直接使用同一 WebVPN 包装 URL 进入学生首页，避免无意义地要求用户手点。
        home_url = _academic_home_url(page.url)
        if "xsMain.html" not in home_url:
            raise RuntimeError("教务系统中转页没有可用的首页地址，真实浏览器已保留在当前页。")
        page.goto(home_url, wait_until="domcontentloaded", timeout=90_000)

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        for candidate in page.context.pages:
            try:
                if candidate.is_closed():
                    continue
                if "xsrkxz.htmlx" not in (candidate.url or "").lower() and not _is_entry_choice_page(candidate):
                    return candidate
            except Exception:
                continue
        page.wait_for_timeout(250)
    raise RuntimeError("点击“进入首页”后未完成跳转，真实浏览器已保留在中转页。")


def _is_timetable_loaded(page) -> bool:
    if any("/xskb/xskb_list.do" in (frame.url or "").lower() for frame in page.frames):
        return True
    text = _visible_text(page)
    return "个人课表信息" in text and "周次" in text and "查询" in text


def _select_all_and_query(page) -> bool:
    selected = False
    query_clicked = False
    for frame in page.frames:
        try:
            selects = frame.locator("select")
            for index in range(min(selects.count(), 20)):
                select = selects.nth(index)
                if not select.is_visible():
                    continue
                labels = [label.strip() for label in select.locator("option").all_text_contents()]
                all_label = next((label for label in labels if label == "全部"), None)
                if all_label:
                    select.select_option(label=all_label)
                    selected = True
        except Exception:
            continue
    for frame in page.frames:
        for selector in (
            'button:has-text("查询")',
            'a:has-text("查询")',
            'input[value*="查询"]',
        ):
            try:
                matches = frame.locator(selector)
                for index in range(min(matches.count(), 8)):
                    candidate = matches.nth(index)
                    if candidate.is_visible():
                        candidate.click(timeout=8_000)
                        query_clicked = True
                        break
                if query_clicked:
                    break
            except Exception:
                continue
        if query_clicked:
            break
    if selected or query_clicked:
        page.wait_for_timeout(1_500)
    return query_clicked


class BrowserSession:
    """保持一个可见的临时 Chromium 会话，并完成两层学校登录。"""

    def __init__(self, profile_dir: Path) -> None:
        self.profile_dir = profile_dir
        self.runtime = None
        self.browser = None
        self.context = None
        self.page = None

    def open(self):
        # 打包版优先显式使用安装目录中的 Chromium，避免误落到用户本机 Python 路径。
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError("尚未安装 Playwright。请先运行：python -m pip install -r requirements.txt") from error

        bundled_chromium = _bundled_chromium_executable()
        self.runtime = sync_playwright().start()
        launch_options = {"headless": False}
        if bundled_chromium:
            launch_options["executable_path"] = str(bundled_chromium)
        try:
            self.browser = self.runtime.chromium.launch(**launch_options)
        except Exception as error:
            if getattr(sys, "frozen", False):
                raise RuntimeError("安装包内的 Chromium 无法启动。请重新下载并安装完整的 Installer。") from error
            raise RuntimeError(
                "当前运行的是开发版，未找到 Playwright Chromium。请使用 Installer 安装的“课表导出器”，"
                "或在开发环境运行：python -m playwright install chromium"
            ) from error
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 960})
        self.page = self.context.new_page()
        self.page.goto(WEBVPN_LOGIN_URL, wait_until="domcontentloaded", timeout=90_000)
        return self.page

    def login_webvpn(self, username: str, password: str):
        if not self.page:
            self.open()
        if get_vpn_auth_state(self.page).get("authenticated"):
            return self.page

        if "webvpn.sdust.edu.cn" not in (self.page.url or ""):
            self.page.goto(WEBVPN_LOGIN_URL, wait_until="domcontentloaded", timeout=90_000)

        if not _has_visible_password(self.page):
            cas_link = _first_visible_locator(
                self.page,
                [
                    'a[href*="cas_login=true"]',
                    'a:has-text("CAS统一身份认证登录")',
                    'a:has-text("统一身份认证")',
                ],
            )
            if not cas_link:
                raise RuntimeError("没有找到 WebVPN 的统一身份认证入口。")
            cas_link.click(timeout=10_000)
            self.page.wait_for_load_state("domcontentloaded", timeout=60_000)

        username_field = _first_visible_locator(
            self.page,
            [
                'input[placeholder*="职工号"]',
                'input[placeholder*="学号"]',
                'input[name="username"]',
                '#username',
                'input[type="text"]',
            ],
        )
        password_field = _password_locator(self.page)
        submit = _first_visible_locator(
            self.page,
            [
                'button:has-text("登 录")',
                'button:has-text("登录")',
                'input[type="submit"]',
            ],
        )
        if not username_field or not password_field or not submit:
            raise RuntimeError("WebVPN 登录表单结构与预期不一致。")

        username_field.fill(username)
        password_field.fill(password)
        submit.click(timeout=10_000)

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            self.page.wait_for_timeout(500)
            if get_vpn_auth_state(self.page).get("authenticated"):
                return self.page
            if _has_visible_password(self.page):
                hint = _login_error_hint(self.page)
                if hint:
                    raise RuntimeError("WebVPN 登录未成功：" + hint)
        raise RuntimeError("等待 WebVPN 登录成功超时，请检查账号、密码或验证码。")

    def open_schedule(self):
        if not self.page:
            raise RuntimeError("浏览器会话尚未打开。")
        state = get_vpn_auth_state(self.page)
        if not state["authenticated"]:
            raise RuntimeError("当前页面还没有检测到 WebVPN 登录成功。")
        return navigate_to_schedule(self.page)

    def login_academic(self, username: str, password: str):
        if not self.page:
            raise RuntimeError("浏览器会话尚未打开。")
        self.page = navigate_to_schedule(self.page)
        self.page.wait_for_timeout(700)
        if not _has_visible_password(self.page):
            return self.page

        username_field, password_field, submit = _academic_login_controls(self.page)
        if not username_field or not password_field or not submit:
            details = _academic_form_diagnostic(self.page)
            raise RuntimeError("教务系统登录表单结构与预期不一致。可见控件：" + details)

        username_field.fill(username)
        password_field.fill(password)
        submit.click(timeout=10_000)

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            self.page.wait_for_timeout(500)
            if not _has_visible_password(self.page):
                return self.page
            hint = _login_error_hint(self.page)
            if hint:
                raise RuntimeError("教务系统登录未成功：" + hint)
        raise RuntimeError("等待教务系统登录成功超时，请检查账号或密码。")

    def open_timetable(self, on_status=None):
        if not self.page:
            raise RuntimeError("浏览器会话尚未打开。")
        if _is_entry_choice_page(self.page):
            if on_status:
                on_status("已进入教务系统中转页，正在点击“进入首页”…")
            self.page = _enter_academic_home(self.page)
        self.page.goto(TIMETABLE_URL, wait_until="domcontentloaded", timeout=90_000)
        self.page.wait_for_timeout(1_000)
        if _is_entry_choice_page(self.page):
            if on_status:
                on_status("正在从中转页进入教务首页…")
            self.page = _enter_academic_home(self.page)
            self.page.goto(TIMETABLE_URL, wait_until="domcontentloaded", timeout=90_000)
            self.page.wait_for_timeout(1_000)
        if _has_visible_password(self.page):
            raise RuntimeError("教务系统登录状态已失效。")

        if not _is_timetable_loaded(self.page):
            self.page.goto(SCHEDULE_URL, wait_until="domcontentloaded", timeout=90_000)
            for label in ("培养服务", "我的课表", "学期理论课表"):
                if _click_text_in_frames(self.page, label):
                    self.page.wait_for_timeout(700)
            self.page.wait_for_timeout(1_000)
        if not _is_timetable_loaded(self.page):
            raise RuntimeError("自动进入学期理论课表失败，真实浏览器已保留在教务系统页面。")

        if on_status:
            on_status("正在将周次设为“全部”并查询课表…")
        _select_all_and_query(self.page)
        return self.page

    def login_and_open_timetable(
        self,
        username: str,
        vpn_password: str,
        academic_password: str,
        on_status=None,
    ):
        if on_status:
            on_status("正在打开 WebVPN…")
        self.open()
        if on_status:
            on_status("正在登录 WebVPN…")
        self.login_webvpn(username, vpn_password)
        if on_status:
            on_status("正在登录教务系统…")
        self.login_academic(username, academic_password)
        return self.open_timetable(on_status=on_status)

    def close(self) -> None:
        if self.context:
            self.context.close()
            self.context = None
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.runtime:
            self.runtime.stop()
            self.runtime = None

def is_vpn_login_page(page_url: str) -> bool:
    """只能作为网址提示；WebVPN 登录成功后仍可能停留在 /login。"""
    return "/login" in (page_url or "").lower()


def get_vpn_auth_state(page) -> dict:
    """根据页面内容而非 URL 判断 WebVPN 是否已登录。"""
    try:
        state = page.evaluate(VPN_AUTH_STATE_SCRIPT)
    except Exception:
        return {"authenticated": False, "dashboard": False, "visiblePassword": False}
    if not isinstance(state, dict):
        return {"authenticated": False, "dashboard": False, "visiblePassword": False}
    return state


def is_vpn_authenticated(page) -> bool:
    return bool(get_vpn_auth_state(page).get("authenticated"))


def navigate_to_schedule(page):
    """认证后在当前标签页直达教务系统，绕开 WebVPN 卡片的 window.open。"""
    page.goto(SCHEDULE_URL, wait_until="domcontentloaded", timeout=90_000)
    return page


def is_schedule_page(page_url: str) -> bool:
    """仅允许在教务系统 jsxsd 页面读取，避免误抓 WebVPN 首页。"""
    return "/jsxsd/" in (page_url or "").lower()


def extract_from_open_page(page) -> dict:
    current_url = page.url
    frame_urls = [frame.url for frame in page.frames]
    if not any(is_schedule_page(url) for url in [current_url, *frame_urls]):
        raise RuntimeError(
            "当前浏览器仍停留在 WebVPN 首页，而不是教务课表页面。\n\n"
            "请先在 WebVPN 首页登录，再点击“教务系统”，进入“培养服务 → 我的课表 → 学期理论课表”。\n"
            "确认浏览器地址栏包含 /jsxsd/、周次为“全部”且课表已显示后，再回到本程序点击确定。\n\n"
            f"当前地址：{current_url}"
        )

    last_result = None
    for attempt in range(6):
        cards = []
        time_map = {}
        frame_diagnostics = []
        seen_cards = set()
        for frame in page.frames:
            try:
                frame_result = frame.evaluate(EXTRACT_PAGE_DATA)
            except Exception as error:
                frame_diagnostics.append(
                    {"url": frame.url, "error": f"{type(error).__name__}: {error}"}
                )
                continue
            frame_cards = frame_result.get("cards", []) if isinstance(frame_result, dict) else []
            frame_time_map = frame_result.get("timeMap", {}) if isinstance(frame_result, dict) else {}
            frame_diagnostics.append(
                {
                    "url": frame.url,
                    "title": frame_result.get("title", ""),
                    "cardCount": len(frame_cards),
                    "timeMapCount": len(frame_time_map),
                }
            )
            for card in frame_cards:
                key = (card.get("weekday", ""), card.get("text", ""))
                if key not in seen_cards:
                    seen_cards.add(key)
                    cards.append(card)
            time_map.update(frame_time_map)

        last_result = {
            "title": page.title(),
            "cards": cards,
            "timeMap": time_map,
            "pageUrl": current_url,
            "frames": frame_diagnostics,
        }
        if cards:
            return last_result
        if attempt < 5:
            page.wait_for_timeout(500)
    return last_result


def save_debug_snapshot(data: dict, target: Path) -> None:
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

