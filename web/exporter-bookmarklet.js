(() => {
  'use strict';

  const LIBRARY_URL = 'https://opingur.github.io/ScheduleClawer_SDUST/vendor/xlsx.bundle.js?v=20260905-1';
  const WEEKDAYS = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'];
  const WEEKDAY_MAP = { '星期一': 1, '周一': 1, '星期二': 2, '周二': 2, '星期三': 3, '周三': 3, '星期四': 4, '周四': 4, '星期五': 5, '周五': 5, '星期六': 6, '周六': 6, '星期日': 7, '星期天': 7, '周日': 7 };
  const PALETTE = ['F9B8C9', 'A9CEF5', 'BCE7D0', 'E6C8F3', 'F8D0A6', 'AEE6E4', 'F6D7A8', 'C9D9F8'];
  const BORDER = { left: { style: 'thin', color: { rgb: 'D5DEEE' } }, right: { style: 'thin', color: { rgb: 'D5DEEE' } }, top: { style: 'thin', color: { rgb: 'D5DEEE' } }, bottom: { style: 'thin', color: { rgb: 'D5DEEE' } } };

  const clean = (value) => String(value || '').replace(/\u00a0/g, ' ').replace(/[ \t]+/g, ' ').trim();
  const compact = (value) => String(value || '').replace(/[\t\r ]+/g, ' ').trim();
  const hasCourseMeta = (value) => /(?:老师|教师)\s*[:：]/.test(value) && /时间\s*[:：]/.test(value);
  const cellRef = (row, column) => XLSX.utils.encode_cell({ r: row - 1, c: column - 1 });
  const range = (firstRow, firstColumn, lastRow, lastColumn) => XLSX.utils.encode_range({ s: { r: firstRow - 1, c: firstColumn - 1 }, e: { r: lastRow - 1, c: lastColumn - 1 } });

  function toast(message, isError = false) {
    const existing = document.getElementById('__sdust_schedule_exporter_toast__');
    if (existing) existing.remove();
    const box = document.createElement('div');
    box.id = '__sdust_schedule_exporter_toast__';
    box.textContent = message;
    Object.assign(box.style, {
      position: 'fixed', zIndex: '2147483647', right: '18px', top: '18px', maxWidth: '360px',
      padding: '12px 15px', color: '#fff', background: isError ? '#b42318' : '#164a9e',
      borderRadius: '5px', boxShadow: '0 10px 28px rgba(0,0,0,.25)', font: '14px/1.5 system-ui, sans-serif'
    });
    document.documentElement.appendChild(box);
    if (isError) setTimeout(() => box.remove(), 9000);
  }

  function discoverDocuments(rootWindow = window, found = [], seen = new Set()) {
    try {
      if (!rootWindow || !rootWindow.document || seen.has(rootWindow.document)) return found;
      seen.add(rootWindow.document);
      found.push(rootWindow.document);
      for (let index = 0; index < rootWindow.frames.length; index += 1) {
        try { discoverDocuments(rootWindow.frames[index], found, seen); } catch (_) { /* 跨域 frame 无法读取，跳过 */ }
      }
    } catch (_) { /* 忽略无法访问的 frame */ }
    return found;
  }

  function hasUsableTitle(value) {
    const marker = value.search(/(?:老师|教师|时间|地点|教室)\s*[:：]/);
    if (marker <= 0) return false;
    return value.slice(0, marker).split(/\n+/).map(clean).filter(Boolean)
      .some((line) => !/^(?:课程编号|班级|总人数|考核方式|总学时|网课群号|网课链接|分组名)\s*[:：]/.test(line));
  }

  function cardTextFor(element, leafText, body) {
    let current = element;
    let best = leafText;
    while (current.parentElement && current.parentElement !== body) {
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
  }

  function headerFor(cell) {
    const table = cell.closest('table');
    if (!table) return '';
    const rows = [...table.querySelectorAll('tr')];
    const index = cell.cellIndex;
    const headerRow = rows.find((row) => /星期[一二三四五六日天]|周[一二三四五六日]/.test(row.innerText || ''));
    return headerRow && headerRow.cells[index] ? clean(headerRow.cells[index].innerText) : '';
  }

  function extractFromDocument(doc) {
    const candidates = [...doc.querySelectorAll('body *')]
      .map((element) => ({ element, text: clean(element.innerText) }))
      .filter(({ text }) => text.length >= 12 && text.length <= 700 && hasCourseMeta(text))
      .filter(({ element }) => ![...element.children].some((child) => hasCourseMeta(clean(child.innerText))))
      .map(({ element, text }) => {
        const cell = element.closest('td');
        return { text: cardTextFor(element, text, doc.body), weekday: cell ? headerFor(cell) : '' };
      })
      .filter((item) => /星期[一二三四五六日天]|周[一二三四五六日]/.test(item.weekday));

    const cards = [...new Map(candidates.map((item) => [item.weekday + '|' + item.text, item])).values()];
    const timeMap = {};
    for (const row of [...doc.querySelectorAll('tr')]) {
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
    return { cards, timeMap };
  }

  function readSchedule() {
    const documents = discoverDocuments();
    const uniqueCards = new Map();
    const timeMap = {};
    for (const doc of documents) {
      const data = extractFromDocument(doc);
      for (const card of data.cards) uniqueCards.set(card.weekday + '|' + card.text, card);
      Object.assign(timeMap, data.timeMap);
    }
    return { cards: [...uniqueCards.values()], timeMap, documentCount: documents.length };
  }

  function parseWeeks(value, maxWeek) {
    const source = String(value || '').replace(/，/g, ',').replace(/至/g, '-');
    if (!source) return Array.from({ length: maxWeek }, (_, index) => index + 1);
    const odd = /单周|\(单\)|（单）/.test(source);
    const even = /双周|\(双\)|（双）/.test(source);
    const weekPart = source.includes('周') ? source.split('周', 1)[0] : source;
    const weeks = new Set();
    for (const match of weekPart.matchAll(/(\d{1,2})\s*(?:-|~|—|–)\s*(\d{1,2})/g)) {
      const low = Math.min(Number(match[1]), Number(match[2]));
      const high = Math.max(Number(match[1]), Number(match[2]));
      for (let week = low; week <= high; week += 1) weeks.add(week);
    }
    const covered = weekPart.replace(/\d{1,2}\s*(?:-|~|—|–)\s*\d{1,2}/g, '');
    for (const valueMatch of covered.matchAll(/\d{1,2}/g)) weeks.add(Number(valueMatch[0]));
    if (!weeks.size) for (let week = 1; week <= maxWeek; week += 1) weeks.add(week);
    return [...weeks].filter((week) => week >= 1 && week <= maxWeek && (!odd || week % 2 === 1) && (!even || week % 2 === 0)).sort((a, b) => a - b);
  }

  function parsePeriods(value) {
    const source = String(value || '');
    let match = source.match(/(?:\[|【|\(|（)\s*(\d{1,2})\s*(?:-|~|—|–|至)\s*(\d{1,2})\s*节?\s*(?:\]|】|\)|）)/);
    if (!match) match = source.match(/(?:第)?\s*(\d{1,2})\s*(?:-|~|—|–|至)\s*(\d{1,2})\s*节/);
    if (match) return [Math.min(Number(match[1]), Number(match[2])), Math.max(Number(match[1]), Number(match[2]))];
    match = source.match(/(?:\[|【|\(|（)\s*(\d{1,2})\s*节?\s*(?:\]|】|\)|）)/);
    return match ? [Number(match[1]), Number(match[1])] : [null, null];
  }

  function field(text, names) {
    const labels = names.map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const boundaries = '老师|教师|时间|地点|教室|课程编号|班级|总人数|考核方式|总学时|网课群号|网课链接|分组名';
    const match = String(text || '').match(new RegExp(`(?:${labels})\\s*[:：]\\s*(.+?)(?=(?:${boundaries})\\s*[:：]|$)`, 's'));
    return match ? match[1].replace(/\s+/g, ' ').replace(/^[ ;；,，]+|[ ;；,，]+$/g, '') : '';
  }

  function courseName(text) {
    const marker = String(text || '').search(/(?:老师|教师|时间|地点|教室)\s*[:：]/);
    const prefix = marker >= 0 ? String(text).slice(0, marker) : String(text || '');
    const ignored = /^(?:课程编号|班级|总人数|考核方式|总学时|网课群号|网课链接|分组名)\s*[:：]/;
    return prefix.split(/\n+/).map(compact).find((line) => line && !ignored.test(line)) || '未识别课程';
  }

  function normalise(cards, timeMap, maxWeek) {
    const rows = [];
    const seen = new Set();
    for (const card of cards) {
      const weekday = WEEKDAY_MAP[compact(card.weekday)];
      const text = card.text || '';
      if (!weekday || !text) continue;
      const teacher = field(text, ['老师', '教师']);
      const sourceTime = field(text, ['时间']);
      const location = field(text, ['地点', '教室']);
      const [startPeriod, endPeriod] = parsePeriods(sourceTime || text);
      const name = courseName(text);
      if (!startPeriod || name === '未识别课程') continue;
      for (const week of parseWeeks(sourceTime, maxWeek)) {
        const item = { week, weekday, courseName: name, teacher, location, startPeriod, endPeriod, startTime: (timeMap[String(startPeriod)] || {}).start || '', endTime: (timeMap[String(endPeriod)] || {}).end || '', sourceTime: compact(sourceTime) };
        const signature = JSON.stringify(item);
        if (!seen.has(signature)) { seen.add(signature); rows.push(item); }
      }
    }
    return rows.sort((a, b) => a.week - b.week || a.weekday - b.weekday || a.startPeriod - b.startPeriod || a.courseName.localeCompare(b.courseName, 'zh-CN'));
  }

  function colorFor(name) {
    let value = 0;
    for (const char of String(name || '')) value = ((value * 31) + char.codePointAt(0)) | 0;
    return PALETTE[(value >>> 0) % PALETTE.length];
  }

  function cardText(item) {
    const clock = item.startTime && item.endTime ? `${item.startTime}–${item.endTime}` : `第${item.startPeriod}–${item.endPeriod}节`;
    return [item.courseName, `${clock}｜第${item.startPeriod}–${item.endPeriod}节`, item.location, item.teacher].filter(Boolean).join('\n');
  }

  const titleStyle = { fill: { patternType: 'solid', fgColor: { rgb: '1E4FA8' } }, font: { bold: true, color: { rgb: 'FFFFFF' }, sz: 15 }, alignment: { horizontal: 'center', vertical: 'center' }, border: BORDER };
  const headerStyle = { fill: { patternType: 'solid', fgColor: { rgb: '2F6BDB' } }, font: { bold: true, color: { rgb: 'FFFFFF' }, sz: 11 }, alignment: { horizontal: 'center', vertical: 'center', wrapText: true }, border: BORDER };
  const timeStyle = { fill: { patternType: 'solid', fgColor: { rgb: 'EEF3FD' } }, font: { bold: true, color: { rgb: '1E4FA8' } }, alignment: { horizontal: 'center', vertical: 'center', wrapText: true }, border: BORDER };
  const gridStyle = (fill) => ({ fill: fill ? { patternType: 'solid', fgColor: { rgb: fill } } : undefined, alignment: { vertical: 'top', wrapText: true }, border: BORDER });

  function put(sheet, row, column, value, style) {
    sheet[cellRef(row, column)] = { t: 's', v: String(value ?? ''), s: style };
  }

  function applyTitle(sheet, title) {
    put(sheet, 1, 1, title, titleStyle);
    sheet['!merges'] = [XLSX.utils.decode_range(range(1, 1, 1, 8))];
    sheet['!rows'] = [{ hpt: 30 }];
  }

  function setWidths(sheet, first, rest) {
    sheet['!cols'] = [{ wch: first }, ...Array.from({ length: 7 }, () => ({ wch: rest }))];
  }

  function dateLabel(termStart, week, weekday) {
    const current = new Date(`${termStart}T00:00:00`);
    current.setDate(current.getDate() + ((week - 1) * 7) + (weekday - 1));
    return `${current.getMonth() + 1}月${current.getDate()}日`;
  }

  function createOverview(courses, weekCount) {
    const sheet = {};
    applyTitle(sheet, '学期课表总览（按实际周次展开）');
    ['周次', ...WEEKDAYS].forEach((value, index) => put(sheet, 3, index + 1, value, headerStyle));
    for (let week = 1; week <= weekCount; week += 1) {
      const row = week + 3;
      put(sheet, row, 1, `第${week}周`, timeStyle);
      for (let day = 1; day <= 7; day += 1) {
        const items = courses.filter((item) => item.week === week && item.weekday === day);
        put(sheet, row, day + 1, items.map(cardText).join('\n\n'), gridStyle(items[0] && colorFor(items[0].courseName)));
      }
      sheet['!rows'][row - 1] = { hpt: Math.max(70, Math.min(180, 34 + Math.max(0, ...Array.from({ length: 7 }, (_, index) => courses.filter((item) => item.week === week && item.weekday === index + 1).length)) * 62)) };
    }
    setWidths(sheet, 10, 27);
    sheet['!ref'] = range(1, 1, weekCount + 3, 8);
    return sheet;
  }

  function periodSlots(current, timeMap) {
    if (!Object.keys(timeMap).length) {
      const seen = new Set();
      return [...current]
        .sort((a, b) => a.startPeriod - b.startPeriod || a.endPeriod - b.endPeriod)
        .filter((item) => {
          const key = `${item.startPeriod}|${item.endPeriod}|${item.startTime}|${item.endTime}`;
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        })
        .map((item) => ({
          startPeriod: item.startPeriod,
          endPeriod: item.endPeriod,
          startTime: item.startTime || '',
          endTime: item.endTime || '',
          key: `${item.startPeriod}|${item.endPeriod}|${item.startTime}|${item.endTime}`,
        }));
    }
    const periods = [...new Set(current.flatMap((item) => Array.from({ length: item.endPeriod - item.startPeriod + 1 }, (_, index) => item.startPeriod + index)))].sort((a, b) => a - b);
    const slots = [];
    for (const period of periods) {
      const time = timeMap[String(period)] || {};
      const key = `${time.start || ''}|${time.end || ''}`;
      const previous = slots[slots.length - 1];
      if (previous && previous.key === key && previous.endPeriod === period - 1) previous.endPeriod = period;
      else slots.push({ startPeriod: period, endPeriod: period, startTime: time.start || '', endTime: time.end || '', key });
    }
    return slots;
  }

  function createWeekSheet(courses, week, termStart, timeMap) {
    const sheet = {};
    applyTitle(sheet, `第${week}周课表`);
    ['日期', ...Array.from({ length: 7 }, (_, index) => dateLabel(termStart, week, index + 1))].forEach((value, index) => put(sheet, 3, index + 1, value, headerStyle));
    ['时间 / 节次', ...WEEKDAYS].forEach((value, index) => put(sheet, 4, index + 1, value, headerStyle));
    const current = courses.filter((item) => item.week === week);
    const slots = periodSlots(current, timeMap);
    if (!slots.length) {
      put(sheet, 5, 1, '本周没有识别到课程', gridStyle());
      sheet['!merges'].push(XLSX.utils.decode_range(range(5, 1, 5, 8)));
      sheet['!rows'][4] = { hpt: 50 };
      setWidths(sheet, 16, 24);
      sheet['!ref'] = range(1, 1, 5, 8);
      return sheet;
    }
    slots.forEach((slot, index) => {
      const row = index + 5;
      const clock = slot.startTime && slot.endTime ? `${slot.startTime}–${slot.endTime}` : '未识别钟点';
      put(sheet, row, 1, `${clock}\n第${slot.startPeriod}–${slot.endPeriod}节`, timeStyle);
      for (let day = 1; day <= 7; day += 1) {
        const items = current.filter((item) => item.weekday === day && item.startPeriod <= slot.startPeriod && item.endPeriod >= slot.endPeriod);
        put(sheet, row, day + 1, items.map(cardText).join('\n\n'), gridStyle(items[0] && colorFor(items[0].courseName)));
      }
      sheet['!rows'][row - 1] = { hpt: Math.max(80, Math.min(180, 34 + Math.max(0, ...Array.from({ length: 7 }, (_, dayIndex) => current.filter((item) => item.weekday === dayIndex + 1 && item.startPeriod <= slot.startPeriod && item.endPeriod >= slot.endPeriod).length)) * 62)) };
    });
    for (let day = 1; day <= 7; day += 1) {
      let start = 0;
      while (start < slots.length) {
        const sameItems = (slot) => current.filter((item) => item.weekday === day && item.startPeriod <= slot.startPeriod && item.endPeriod >= slot.endPeriod).map(cardText);
        const signature = JSON.stringify(sameItems(slots[start]));
        let end = start;
        while (end + 1 < slots.length && JSON.stringify(sameItems(slots[end + 1])) === signature) end += 1;
        if (signature !== '[]' && end > start) sheet['!merges'].push(XLSX.utils.decode_range(range(start + 5, day + 1, end + 5, day + 1)));
        start = end + 1;
      }
    }
    setWidths(sheet, 16, 24);
    sheet['!ref'] = range(1, 1, slots.length + 4, 8);
    return sheet;
  }

  function createDetails(courses) {
    const sheet = {};
    const headers = ['周次', '星期', '课程名称', '具体时间', '节次', '教师', '地点', '教务系统时间原文'];
    headers.forEach((value, index) => put(sheet, 1, index + 1, value, headerStyle));
    courses.forEach((item, index) => {
      const row = index + 2;
      const clock = item.startTime && item.endTime ? `${item.startTime}–${item.endTime}` : '未识别钟点';
      [`第${item.week}周`, WEEKDAYS[item.weekday - 1], item.courseName, clock, `第${item.startPeriod}–${item.endPeriod}节`, item.teacher, item.location, item.sourceTime].forEach((value, column) => put(sheet, row, column + 1, value, gridStyle()));
      sheet['!rows'] = sheet['!rows'] || [];
      sheet['!rows'][row - 1] = { hpt: 28 };
    });
    sheet['!cols'] = [10, 10, 26, 16, 13, 16, 28, 30].map((wch) => ({ wch }));
    sheet['!autofilter'] = { ref: range(1, 1, Math.max(2, courses.length + 1), 8) };
    sheet['!ref'] = range(1, 1, Math.max(2, courses.length + 1), 8);
    return sheet;
  }

  function buildWorkbook(courses, timeMap, config) {
    const book = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(book, createOverview(courses, config.weekCount), '20周总览');
    for (let week = 1; week <= config.weekCount; week += 1) XLSX.utils.book_append_sheet(book, createWeekSheet(courses, week, config.termStartMonday, timeMap), `第${week}周`);
    XLSX.utils.book_append_sheet(book, createDetails(courses), '课程明细');
    return book;
  }

  function loadLibrary() {
    if (window.XLSX) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = LIBRARY_URL;
      script.async = true;
      script.onload = () => window.XLSX ? resolve() : reject(new Error('Excel 组件未正确加载。请返回网页点击“更新书签设置”，替换旧收藏后重试。'));
      script.onerror = () => reject(new Error('Excel 组件加载失败。请检查网络后重试。'));
      document.head.appendChild(script);
    });
  }

  async function run(rawConfig) {
    const config = { weekCount: Number(rawConfig && rawConfig.weekCount) || 20, termStartMonday: String(rawConfig && rawConfig.termStartMonday || '') };
    if (config.weekCount < 1 || config.weekCount > 30) throw new Error('书签中的周数设置无效，请回到工具页重新创建书签。');
    const monday = new Date(`${config.termStartMonday}T00:00:00`);
    if (Number.isNaN(monday.getTime()) || monday.getDay() !== 1) throw new Error('书签中的第 1 周日期无效，请回到工具页重新创建书签。');
    if (!/jsxsd|学期理论课表|个人课表信息/.test(`${location.href} ${document.body ? document.body.innerText : ''}`)) throw new Error('请在山东科技大学“学期理论课表”已显示的页面点击书签。');

    toast('正在读取当前课表…');
    const raw = readSchedule();
    const courses = normalise(raw.cards, raw.timeMap, config.weekCount);
    if (!courses.length) throw new Error('没有识别到课程。请确认周次为“全部”、课表已显示后再点击书签。');
    toast(`已读取 ${courses.length} 条课程记录，正在生成 Excel…`);
    await loadLibrary();
    const book = buildWorkbook(courses, raw.timeMap, config);
    XLSX.writeFile(book, `山科课表_${config.termStartMonday}.xlsx`, { compression: true });
    toast(`导出完成：${courses.length} 条课程记录。`);
  }

  window.SDUSTScheduleExporter = { run: (config) => run(config).catch((error) => { console.error('[SDUST schedule exporter]', error); toast(error.message || '导出失败，请重新检查课表页面。', true); }) };
})();