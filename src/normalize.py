from __future__ import annotations

import re
from collections.abc import Iterable


WEEKDAY_MAP = {
    "星期一": 1,
    "周一": 1,
    "星期二": 2,
    "周二": 2,
    "星期三": 3,
    "周三": 3,
    "星期四": 4,
    "周四": 4,
    "星期五": 5,
    "周五": 5,
    "星期六": 6,
    "周六": 6,
    "星期日": 7,
    "星期天": 7,
    "周日": 7,
}


def _compact(value: str) -> str:
    return re.sub(r"[\t\r ]+", " ", value or "").strip()


def parse_weeks(week_text: str, max_week: int) -> list[int]:
    """把 1-8周、1,3,5周、1-16周(单) 等表达式展开为实际周次。"""
    source = (week_text or "").replace("，", ",").replace("至", "-")
    if not source:
        return list(range(1, max_week + 1))

    odd = bool(re.search(r"单周|\(单\)|（单）", source))
    even = bool(re.search(r"双周|\(双\)|（双）", source))
    # “周”之后通常是 [1-2节]；节次数字绝不能参与周次展开。
    week_part = source.split("周", 1)[0] if "周" in source else source
    weeks: set[int] = set()
    for start, end in re.findall(r"(\d{1,2})\s*(?:-|~|—|–)\s*(\d{1,2})", week_part):
        low, high = sorted((int(start), int(end)))
        weeks.update(range(low, high + 1))

    # 剩余的独立数字，如 1,3,5周。
    covered = re.sub(r"\d{1,2}\s*(?:-|~|—|–)\s*\d{1,2}", "", week_part)
    weeks.update(int(value) for value in re.findall(r"\d{1,2}", covered))
    if not weeks:
        weeks.update(range(1, max_week + 1))
    if odd:
        weeks = {week for week in weeks if week % 2 == 1}
    if even:
        weeks = {week for week in weeks if week % 2 == 0}
    return sorted(week for week in weeks if 1 <= week <= max_week)


def parse_periods(value: str) -> tuple[int | None, int | None]:
    # 教务格式一般为“1-8周[1-2节]”；优先读取方括号内节次。
    match = re.search(
        r"(?:\[|【|\(|（)\s*(\d{1,2})\s*(?:-|~|—|–|至)\s*(\d{1,2})\s*节?\s*(?:\]|】|\)|）)",
        value or "",
    )
    if match:
        first, last = int(match.group(1)), int(match.group(2))
        return min(first, last), max(first, last)
    # 非括号格式必须明确带“节”，避免把“1-8周”误认成第1-8节。
    match = re.search(r"(?:第)?\s*(\d{1,2})\s*(?:-|~|—|–|至)\s*(\d{1,2})\s*节", value or "")
    if match:
        first, last = int(match.group(1)), int(match.group(2))
        return min(first, last), max(first, last)
    match = re.search(r"(?:\[|【|\(|（)\s*(\d{1,2})\s*节?\s*(?:\]|】|\)|）)", value or "")
    if match:
        return int(match.group(1)), int(match.group(1))
    return None, None


def _field(text: str, names: Iterable[str]) -> str:
    label = "|".join(re.escape(name) for name in names)
    boundary_labels = (
        "老师|教师|时间|地点|教室|课程编号|班级|总人数|考核方式|"
        "总学时|网课群号|网课链接|分组名"
    )
    match = re.search(
        rf"(?:{label})\s*[:：]\s*(.+?)(?=(?:{boundary_labels})\s*[:：]|$)",
        text,
        flags=re.S,
    )
    return re.sub(r"\s+", " ", match.group(1)).strip(" ;；,，") if match else ""


def _course_name(text: str) -> str:
    first_label = re.search(r"(?:老师|教师|时间|地点|教室)\s*[:：]", text)
    prefix = text[: first_label.start()] if first_label else text
    lines = [_compact(line) for line in prefix.splitlines() if _compact(line)]
    ignored = re.compile(
        r"^(?:课程编号|班级|总人数|考核方式|总学时|网课群号|网课链接|分组名)\s*[:：]"
    )
    for line in lines:
        if not ignored.search(line):
            return line
    return "未识别课程"


def normalise_cards(cards: list[dict], time_map: dict[str, dict], max_week: int) -> list[dict]:
    """将网页卡片转换成按周展开的标准课程记录。"""
    result: list[dict] = []
    seen: set[tuple] = set()
    for card in cards:
        text = card.get("text", "")
        weekday = WEEKDAY_MAP.get(_compact(card.get("weekday", "")))
        if not text or not weekday:
            continue
        teacher = _field(text, ("老师", "教师"))
        time_field = _field(text, ("时间",))
        location = _field(text, ("地点", "教室"))
        start_period, end_period = parse_periods(time_field or text)
        time_info = time_map.get(str(start_period), {}) if start_period else {}
        start_time = time_info.get("start", "")
        end_time = time_map.get(str(end_period), {}).get("end", "") if end_period else ""
        name = _course_name(text)
        if name == "未识别课程" or not start_period:
            continue

        for week in parse_weeks(time_field, max_week):
            item = {
                "week": week,
                "weekday": weekday,
                "courseName": name,
                "teacher": teacher,
                "location": location,
                "startPeriod": start_period,
                "endPeriod": end_period,
                "startTime": start_time,
                "endTime": end_time,
                "sourceTime": _compact(time_field),
            }
            signature = tuple(item.values())
            if signature not in seen:
                seen.add(signature)
                result.append(item)
    return sorted(result, key=lambda value: (value["week"], value["weekday"], value["startPeriod"], value["courseName"]))

