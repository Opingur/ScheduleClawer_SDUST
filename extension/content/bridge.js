(() => {
  'use strict';

  if (globalThis.__scheduleExporterBridgeInstalled) return;
  globalThis.__scheduleExporterBridgeInstalled = true;

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || message.type !== 'EXPORT_CURRENT_SCHEDULE') return undefined;
    if (!window.SDUSTScheduleExporter || typeof window.SDUSTScheduleExporter.run !== 'function') {
      sendResponse({ ok: false, error: '导出组件尚未准备完成，请重新点击导出。' });
      return undefined;
    }

    window.SDUSTScheduleExporter.run(message.config)
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => {
        console.error('[schedule-exporter-extension]', error);
        sendResponse({ ok: false, error: error && error.message ? error.message : '导出失败，请确认课表已显示。' });
      });
    return true;
  });
})();
