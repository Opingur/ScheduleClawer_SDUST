(() => {
  'use strict';

  const api = chrome;
  const weekCount = document.querySelector('#week-count');
  const termStartMonday = document.querySelector('#term-start-monday');
  const exportButton = document.querySelector('#export');
  const status = document.querySelector('#status');
  const STORAGE_KEYS = ['weekCount', 'termStartMonday'];

  function setStatus(message, type = '') {
    status.textContent = message;
    status.className = `status ${type}`.trim();
  }

  function configFromInputs() {
    const config = {
      weekCount: Number(weekCount.value),
      termStartMonday: termStartMonday.value
    };
    if (!Number.isInteger(config.weekCount) || config.weekCount < 1 || config.weekCount > 30) {
      throw new Error('学期总周数应为 1–30。');
    }
    const monday = new Date(`${config.termStartMonday}T00:00:00`);
    if (!config.termStartMonday || Number.isNaN(monday.getTime()) || monday.getDay() !== 1) {
      throw new Error('请填写学校校历中的第 1 周周一。');
    }
    return config;
  }

  async function restoreConfig() {
    const saved = await api.storage.local.get(STORAGE_KEYS);
    if (saved.weekCount) weekCount.value = saved.weekCount;
    if (saved.termStartMonday) termStartMonday.value = saved.termStartMonday;
  }

  async function getActiveHttpTab() {
    const [tab] = await api.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id || !/^https?:/.test(tab.url || '')) {
      throw new Error('请先切换到已打开课表的网页标签页。');
    }
    return tab;
  }

  async function injectExporter(tabId) {
    await api.scripting.executeScript({
      target: { tabId, allFrames: false },
      files: ['vendor/xlsx.bundle.js', 'content/exporter-core.js', 'content/bridge.js']
    });
  }

  async function exportCurrentTab() {
    const config = configFromInputs();
    await api.storage.local.set(config);
    const tab = await getActiveHttpTab();
    setStatus('正在连接当前课表页面…');
    await injectExporter(tab.id);
    setStatus('正在读取课表并生成 Excel…');
    const response = await api.tabs.sendMessage(tab.id, { type: 'EXPORT_CURRENT_SCHEDULE', config });
    if (!response || !response.ok) throw new Error(response && response.error ? response.error : '页面没有返回导出结果。');
    return response.result;
  }

  exportButton.addEventListener('click', async () => {
    exportButton.disabled = true;
    try {
      const result = await exportCurrentTab();
      setStatus(`已导出 ${result.courseCount} 条课程：${result.filename}`, 'success');
    } catch (error) {
      console.error('[schedule-exporter-popup]', error);
      setStatus(error && error.message ? error.message : '导出失败，请确认课表已显示。', 'error');
    } finally {
      exportButton.disabled = false;
    }
  });

  restoreConfig().catch((error) => setStatus(`无法读取本地设置：${error.message}`, 'error'));
})();
