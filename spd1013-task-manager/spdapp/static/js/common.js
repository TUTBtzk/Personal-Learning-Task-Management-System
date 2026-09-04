/* 全站共用的小工具：CSRF 令牌读取、统计数字就地刷新、二次确认。
   base.html 里加载，dashboard.js 与 tasks.js 都通过 window.SPD 调用。 */
window.SPD = (function () {
  'use strict';

  /* AJAX 写操作要带 CSRF 令牌，令牌由 base.html 的 <meta name="csrf-token"> 提供 */
  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  /* 把 /api/stats 返回的 summary 写回页面上所有带 data-stat 的位置，
     统计卡片、列表页汇总条、导航栏铃铛角标一次全部同步，不用整页刷新 */
  function updateSummary(summary) {
    if (!summary) { return; }

    Object.keys(summary).forEach(function (key) {
      document.querySelectorAll('[data-stat="' + key + '"]').forEach(function (el) {
        el.textContent = summary[key];
      });
      document.querySelectorAll('[data-stat-bar="' + key + '"]').forEach(function (el) {
        el.style.width = summary[key] + '%';
        el.setAttribute('aria-valuenow', summary[key]);
      });
    });

    var badge = document.getElementById('reminderBadge');
    if (badge && summary.overdue !== undefined) {
      var count = summary.overdue + summary.due_today + summary.due_soon;
      badge.textContent = count;
      badge.classList.toggle('d-none', count === 0);
    }
  }

  /* 带 data-confirm 属性的表单统一弹二次确认，避免误删 */
  document.addEventListener('submit', function (ev) {
    var form = ev.target;
    var text = form && form.getAttribute && form.getAttribute('data-confirm');
    if (text && !window.confirm(text)) {
      ev.preventDefault();
    }
  });

  return { csrfToken: csrfToken, updateSummary: updateSummary };
})();
