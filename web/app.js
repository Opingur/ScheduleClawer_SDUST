(() => {
  const SCRIPT_URL = 'https://opingur.github.io/ScheduleClawer_SDUST/exporter-bookmarklet.js?v=20260905-1';
  const weekInput = document.querySelector('#week-count');
  const dateInput = document.querySelector('#term-start');
  const bookmark = document.querySelector('#bookmarklet');
  const validation = document.querySelector('#validation-message');
  const copyStatus = document.querySelector('#copy-status');

  function getConfig() {
    const weekCount = Number.parseInt(weekInput.value, 10);
    const termStartMonday = dateInput.value;
    if (!Number.isInteger(weekCount) || weekCount < 1 || weekCount > 30) {
      throw new Error('学期总周数需要在 1 到 30 之间。');
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(termStartMonday)) {
      throw new Error('请填写第 1 周周一日期。');
    }
    const date = new Date(`${termStartMonday}T00:00:00`);
    if (Number.isNaN(date.getTime()) || date.getDay() !== 1) {
      throw new Error('第 1 周日期必须填写周一。');
    }
    return { weekCount, termStartMonday };
  }

  function makeBookmarklet(config) {
    const loader = `(()=>{const c=${JSON.stringify(config)};const u=${JSON.stringify(SCRIPT_URL)};const old=document.getElementById('__sdust_schedule_exporter__');if(old)old.remove();const s=document.createElement('script');s.id='__sdust_schedule_exporter__';s.src=u+'?v=1.0.0';s.async=true;s.onload=()=>window.SDUSTScheduleExporter&&window.SDUSTScheduleExporter.run(c);s.onerror=()=>alert('课表导出脚本加载失败。请确认网络正常，并从项目主页重新添加书签。');document.head.appendChild(s)})()`;
    return `javascript:${loader}`;
  }

  function refresh() {
    try {
      const config = getConfig();
      bookmark.href = makeBookmarklet(config);
      validation.textContent = '';
      copyStatus.textContent = '书签已按当前设置更新。';
      return true;
    } catch (error) {
      validation.textContent = error.message;
      copyStatus.textContent = '';
      return false;
    }
  }

  async function copyBookmark() {
    if (!refresh()) return;
    const text = bookmark.href;
    try {
      await navigator.clipboard.writeText(text);
      copyStatus.textContent = '已复制。新建浏览器收藏后，将内容粘贴到“网址”栏。';
    } catch (_) {
      const helper = document.createElement('textarea');
      helper.value = text;
      helper.setAttribute('readonly', '');
      helper.style.position = 'fixed';
      helper.style.opacity = '0';
      document.body.appendChild(helper);
      helper.select();
      const copied = document.execCommand('copy');
      helper.remove();
      copyStatus.textContent = copied ? '已复制。新建浏览器收藏后，将内容粘贴到“网址”栏。' : '浏览器未授予复制权限，请手动复制书签链接。';
    }
  }

  document.querySelector('#refresh-bookmark').addEventListener('click', refresh);
  document.querySelector('#copy-bookmark').addEventListener('click', copyBookmark);
  weekInput.addEventListener('change', refresh);
  dateInput.addEventListener('change', refresh);
  refresh();
})();