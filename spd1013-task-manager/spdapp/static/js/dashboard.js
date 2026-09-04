/* 仪表盘图表：Chart.js 4
   姓名 佟政慷 · 学号 239001013 · 项目标识 SPD-1013

   首屏用服务端注入的 JSON 直接画，点「刷新数据」时改走 /api/stats，
   刷新一律走 chart.update()，不重新 new Chart（详见文件末尾注释）。 */
(function () {
  'use strict';

  var holder = document.getElementById('statsData');
  if (!holder || typeof Chart === 'undefined') { return; }

  var stats;
  try {
    stats = JSON.parse(holder.textContent);
  } catch (err) {
    console.error('统计数据解析失败：', err);
    return;
  }

  var charts = {};
  var GRID = 'rgba(140, 155, 180, .16)';
  var DONE_COLOR = '#198754';
  var UNDONE_COLOR = '#0d6efd';

  Chart.defaults.font.family = '"Microsoft YaHei", "PingFang SC", "Segoe UI", system-ui, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = '#5a6a85';
  // 容器高度交给 CSS，关掉等比缩放，否则画布会被越拉越长
  Chart.defaults.maintainAspectRatio = false;

  function ctx(id) {
    var canvas = document.getElementById(id);
    return canvas ? canvas.getContext('2d') : null;
  }

  /* 空数据时在画布上盖一层提示：全是 0 的图表画出来是一片空白，容易被当成坏了 */
  function markEmpty(canvasId, isEmpty) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) { return; }
    var box = canvas.parentNode;
    var tip = box.querySelector('.spd-chart-empty');
    if (isEmpty && !tip) {
      tip = document.createElement('div');
      tip.className = 'spd-chart-empty';
      tip.textContent = '暂无数据';
      box.appendChild(tip);
    } else if (!isEmpty && tip) {
      box.removeChild(tip);
    }
  }
  /* ① 完成情况占比：环形图 */
  function buildStatus(summary) {
    var c = ctx('chartStatus');
    if (!c) { return; }
    charts.status = new Chart(c, {
      type: 'doughnut',
      data: {
        labels: ['已完成', '未完成'],
        datasets: [{
          data: [summary.done, summary.undone],
          backgroundColor: [DONE_COLOR, UNDONE_COLOR],
          borderColor: '#fff',
          borderWidth: 2
        }]
      },
      options: {
        cutout: '62%',
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            callbacks: {
              label: function (item) {
                var total = summary.total || 0;
                var pct = total ? (item.parsed / total * 100).toFixed(1) : '0.0';
                return item.label + ' ' + item.parsed + ' 条（' + pct + '%）';
              }
            }
          },
          title: {
            display: true,
            text: '总计 ' + summary.total + ' 条 · 完成率 ' + summary.completion_rate + '%'
          }
        }
      }
    });
    markEmpty('chartStatus', !summary.total);
  }

  /* ② 各课程任务分布：堆叠柱状图，未完成用课程自己的颜色 */
  function buildCourse(byCourse) {
    var c = ctx('chartCourse');
    if (!c) { return; }
    charts.course = new Chart(c, {
      type: 'bar',
      data: {
        labels: byCourse.map(function (x) { return x.name; }),
        datasets: [
          { label: '已完成', data: byCourse.map(function (x) { return x.done; }),
            backgroundColor: DONE_COLOR, borderRadius: 3, stack: 's' },
          { label: '未完成', data: byCourse.map(function (x) { return x.undone; }),
            backgroundColor: byCourse.map(function (x) { return x.color; }),
            borderRadius: 3, stack: 's' }
        ]
      },
      options: {
        scales: {
          x: { grid: { display: false }, ticks: { autoSkip: false, maxRotation: 30 } },
          y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: GRID } }
        },
        plugins: { legend: { position: 'bottom' } }
      }
    });
    markEmpty('chartCourse', !byCourse.length);
  }
  /* ③ 优先级分布：横向柱状图（高/中/低固定三根，某级为 0 也占位） */
  function buildPriority(byPriority) {
    var c = ctx('chartPriority');
    if (!c) { return; }
    charts.priority = new Chart(c, {
      type: 'bar',
      data: {
        labels: byPriority.map(function (x) { return x.label; }),
        datasets: [{
          label: '任务数',
          data: byPriority.map(function (x) { return x.count; }),
          backgroundColor: byPriority.map(function (x) { return x.color; }),
          borderRadius: 4,
          barThickness: 26
        }]
      },
      options: {
        indexAxis: 'y',
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: GRID } },
          y: { grid: { display: false } }
        },
        plugins: { legend: { display: false } }
      }
    });
  }

  /* ④ 近 N 天完成趋势：折线图，缺失日期已在服务端补 0 */
  function buildTrend(trend) {
    var c = ctx('chartTrend');
    if (!c) { return; }
    charts.trend = new Chart(c, {
      type: 'line',
      data: {
        labels: trend.map(function (x) { return x.label; }),
        datasets: [{
          label: '当日完成数',
          data: trend.map(function (x) { return x.count; }),
          borderColor: UNDONE_COLOR,
          backgroundColor: 'rgba(13, 110, 253, .12)',
          fill: true,
          tension: 0.32,
          pointRadius: 3,
          pointBackgroundColor: UNDONE_COLOR
        }]
      },
      options: {
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: GRID } }
        },
        plugins: { legend: { display: false } }
      }
    });
  }
  function statusTitle(summary) {
    return '总计 ' + summary.total + ' 条 · 完成率 ' + summary.completion_rate + '%';
  }

  /* 刷新只改 data 再 update()，不对同一个 canvas 重新 new Chart（见文件末尾说明） */
  function applyUpdate(data) {
    if (charts.status) {
      charts.status.data.datasets[0].data = [data.summary.done, data.summary.undone];
      charts.status.options.plugins.title.text = statusTitle(data.summary);
      charts.status.update();
      markEmpty('chartStatus', !data.summary.total);
    }
    if (charts.course) {
      charts.course.data.labels = data.by_course.map(function (x) { return x.name; });
      charts.course.data.datasets[0].data = data.by_course.map(function (x) { return x.done; });
      charts.course.data.datasets[1].data = data.by_course.map(function (x) { return x.undone; });
      charts.course.data.datasets[1].backgroundColor =
        data.by_course.map(function (x) { return x.color; });
      charts.course.update();
      markEmpty('chartCourse', !data.by_course.length);
    }
    if (charts.priority) {
      charts.priority.data.labels = data.by_priority.map(function (x) { return x.label; });
      charts.priority.data.datasets[0].data =
        data.by_priority.map(function (x) { return x.count; });
      charts.priority.update();
    }
    if (charts.trend) {
      charts.trend.data.labels = data.trend.map(function (x) { return x.label; });
      charts.trend.data.datasets[0].data = data.trend.map(function (x) { return x.count; });
      charts.trend.update();
    }
    if (window.SPD) { window.SPD.updateSummary(data.summary); }
  }

  /* 从 REST 接口取最新数据：页面和 /api/stats 同源，数字永远一致 */
  function refresh(button) {
    var url = (button && button.getAttribute('data-url')) || '/api/stats';
    if (button) { button.disabled = true; }
    fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (resp) { return resp.json(); })
      .then(function (res) {
        if (res.code === 0) { applyUpdate(res.data); }
      })
      .catch(function (err) { console.error('刷新统计失败：', err); })
      .then(function () { if (button) { button.disabled = false; } });
  }
  /* ---------- 初始化 ---------- */
  buildStatus(stats.summary);
  buildCourse(stats.by_course);
  buildPriority(stats.by_priority);
  buildTrend(stats.trend);

  var refreshBtn = document.getElementById('refreshStats');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', function () { refresh(refreshBtn); });
  }

  // 暴露出去，便于在控制台或其它页面脚本里手动刷新
  window.spdDashboard = { charts: charts, refresh: refresh, apply: applyUpdate };

  /* 踩过的坑：一开始「刷新」是直接再 new Chart(同一个 canvas)，
     第二次点击就报 Canvas is already in use - Chart with ID '0' must be destroyed，
     图表整个消失。原因是 Chart.js 会按 canvas 注册实例，同一画布不能挂两个。
     正确做法就是本文件的写法：实例存在 charts 里，刷新只改 data 后调用 update()，
     既没有报错，也保留了过渡动画（要销毁重建则必须先 chart.destroy()）。 */
})();
