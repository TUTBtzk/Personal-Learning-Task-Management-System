/* 任务列表页与表单页的交互：AJAX 标记完成、删除二次确认、智能分类建议、
   快捷日期、字数统计。姓名 佟政慷 · 学号 239001013 · SPD-1013 */
(function () {
  'use strict';

  var STATES = ['done', 'overdue', 'today', 'soon', 'normal'];

  /* 剩余天数按浏览器本地日期算，勾选/取消勾选后立刻更新，不用刷新页面 */
  function dueText(due) {
    if (!due) { return ''; }
    var parts = due.split('-');
    var target = new Date(+parts[0], +parts[1] - 1, +parts[2]);
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var days = Math.round((target - today) / 86400000);
    if (days < 0) { return '逾期 ' + (-days) + ' 天'; }
    if (days === 0) { return '今天到期'; }
    return '还有 ' + days + ' 天';
  }

  /* 把后端返回的新状态写回这一行：状态徽章、行左侧色条、标题删除线、剩余天数 */
  function applyToggle(box, data) {
    var row = box.closest('[data-task-row]');
    if (!row) { return; }

    STATES.forEach(function (s) { row.classList.remove('spd-row-' + s); });
    row.classList.add('spd-row-' + data.state);

    var badge = row.querySelector('[data-state-badge]');
    if (badge) {
      badge.textContent = data.state_label;
      badge.className = 'badge text-bg-' + data.state_color;
    }

    var title = row.querySelector('.spd-task-title');
    if (title) { title.classList.toggle('spd-done', data.status === 1); }

    var left = row.querySelector('[data-days-left]');
    if (left) {
      left.textContent = data.status === 1 ? '已完成' : dueText(row.getAttribute('data-due'));
    }

    // 统计卡片 / 汇总条 / 铃铛角标一起刷新（数据来自同一次响应）
    window.SPD.updateSummary(data.summary);
  }
  /* 勾选复选框即标记完成：POST + X-CSRF-Token，失败时把勾选状态回滚 */
  document.querySelectorAll('.spd-toggle').forEach(function (box) {
    box.addEventListener('change', function () {
      box.disabled = true;
      fetch(box.getAttribute('data-toggle-url'), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRF-Token': window.SPD.csrfToken(), Accept: 'application/json' }
      })
        .then(function (resp) {
          if (!resp.ok) { throw new Error('HTTP ' + resp.status); }
          return resp.json();
        })
        .then(function (res) {
          if (res.code !== 0) { throw new Error(res.msg || '未知错误'); }
          applyToggle(box, res.data);
        })
        .catch(function (err) {
          box.checked = !box.checked;
          window.alert('操作失败：' + err.message + '\n请刷新页面后重试');
        })
        .then(function () { box.disabled = false; });
    });
  });

  /* 删除：把标题和提交地址填进共用的模态框，真正的删除是带令牌的 POST 表单 */
  var delModalEl = document.getElementById('delModal');
  if (delModalEl) {
    var delModal = new bootstrap.Modal(delModalEl);
    var delForm = document.getElementById('delForm');
    var delTitle = document.getElementById('delTitle');
    document.querySelectorAll('.spd-del').forEach(function (btn) {
      btn.addEventListener('click', function () {
        delForm.setAttribute('action', btn.getAttribute('data-del-url'));
        delTitle.textContent = btn.getAttribute('data-del-title');
        delModal.show();
      });
    });
  }

  /* 新增后跳回列表会带 ?highlight=id，把那一行滚到可视区域 */
  var hl = document.querySelector('.spd-row-hl');
  if (hl && hl.scrollIntoView) {
    hl.scrollIntoView({ block: 'center' });
  }
  /* ---------- 表单页：智能分类建议 ---------- */
  var suggestBox = document.getElementById('suggestBox');
  var titleInput = document.getElementById('title');
  if (suggestBox && titleInput) {
    var suggestText = document.getElementById('suggestText');
    var applyBtn = document.getElementById('applySuggest');
    var suggestion = null;
    var lastQuery = '';

    function askSuggest() {
      var title = titleInput.value.trim();
      if (title.length < 2 || title === lastQuery) { return; }
      lastQuery = title;
      var url = suggestBox.getAttribute('data-url') + '?title=' + encodeURIComponent(title);
      fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
        .then(function (resp) { return resp.json(); })
        .then(function (res) {
          if (res.code !== 0 || !res.data || !res.data.matched) {
            suggestBox.classList.add('d-none');
            return;
          }
          suggestion = res.data;
          suggestText.textContent = suggestion.reason +
            '（建议课程：' + (suggestion.course_name || '未分类') +
            '，优先级：' + suggestion.priority_label + '）';
          suggestBox.classList.remove('d-none');
        })
        .catch(function () { suggestBox.classList.add('d-none'); });
    }

    titleInput.addEventListener('blur', askSuggest);
    titleInput.addEventListener('change', askSuggest);

    applyBtn.addEventListener('click', function () {
      if (!suggestion) { return; }
      var courseSelect = document.getElementById('course_id');
      if (courseSelect && suggestion.course_id) {
        courseSelect.value = String(suggestion.course_id);
      }
      var radio = document.getElementById('p' + suggestion.priority);
      if (radio) { radio.checked = true; }
      suggestText.textContent = '已采纳建议，可继续手动调整。';
      applyBtn.disabled = true;
    });
  }
  /* ---------- 表单页：快捷日期按钮 ---------- */
  var dueInput = document.getElementById('due_date');
  document.querySelectorAll('.spd-quickdate .btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (!dueInput) { return; }
      var d = new Date();
      d.setDate(d.getDate() + parseInt(btn.getAttribute('data-days'), 10));
      // 用本地年月日拼字符串，不用 toISOString（那是 UTC，跨时区会差一天）
      var m = ('0' + (d.getMonth() + 1)).slice(-2);
      var day = ('0' + d.getDate()).slice(-2);
      dueInput.value = d.getFullYear() + '-' + m + '-' + day;
    });
  });

  /* ---------- 表单页：字数统计 ---------- */
  document.querySelectorAll('[data-counter]').forEach(function (field) {
    var out = document.getElementById(field.getAttribute('data-counter'));
    if (!out) { return; }
    field.addEventListener('input', function () {
      out.textContent = field.value.length;
      out.parentNode.classList.toggle(
        'text-danger', field.value.length > (field.id === 'note' ? 200 : 50));
    });
  });
})();
