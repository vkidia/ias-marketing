(function () {
  'use strict';

  // ── Цветовая палитра ─────────────────────────────────────────────────────

  const P = {
    blue:   '#0d6efd',
    green:  '#198754',
    cyan:   '#0dcaf0',
    orange: '#fd7e14',
    purple: '#6610f2',
    red:    '#dc3545',
    gray:   '#6c757d',
    teal:   '#20c997',
  };
  const PALETTE = Object.values(P);

  const FUNNEL_COLORS = [P.gray, P.cyan, P.blue, P.green, P.red];
  const FUNNEL_LABELS = ['Новый', 'Связались', 'Квалифицирован', 'Конвертирован', 'Потерян'];
  const FUNNEL_KEYS   = ['new', 'contacted', 'qualified', 'converted', 'lost'];

  // ── DSS уровни ───────────────────────────────────────────────────────────

  const LEVEL_ORDER = { danger: 3, warning: 2, info: 1, success: 0 };
  const LEVEL_CARD = {
    danger:  ['border-danger',   'bg-danger',   'text-white',  'bi-exclamation-triangle-fill text-danger'],
    warning: ['border-warning',  'bg-warning',  'text-dark',   'bi-exclamation-circle-fill text-warning'],
    info:    ['border-info',     'bg-info',     'text-white',  'bi-info-circle-fill text-info'],
    success: ['border-success',  'bg-success',  'text-white',  'bi-check-circle-fill text-success'],
  };
  const LEVEL_ROW = {
    danger:  ['border-danger',   'text-danger-emphasis',   'bg-danger-subtle'],
    warning: ['border-warning',  'text-warning-emphasis',  'bg-warning-subtle'],
    info:    ['border-info',     'text-info-emphasis',     'bg-info-subtle'],
    success: ['border-success',  'text-success-emphasis',  'bg-success-subtle'],
  };

  // ── Состояние выбранных кампаний ─────────────────────────────────────────

  let selectedIds   = [];  // пустой = все кампании
  let selectedNames = [];

  // ── Chart.js инстансы ────────────────────────────────────────────────────

  let charts = {};

  function buildCharts(data) {
    Object.values(charts).forEach(c => c.destroy());
    charts = {};

    const isCompare = data.mode === 'compare';

    // Линейный — динамика лидов (один dataset или несколько для сравнения)
    const monthlyDatasets = isCompare
      ? data.monthly_datasets
      : [{
          label: 'Новых лидов',
          data: data.monthly_data,
          borderColor: P.blue,
          backgroundColor: 'rgba(13,110,253,0.07)',
          fill: true,
          tension: 0.35,
          pointRadius: 5,
          pointHoverRadius: 7,
          pointBackgroundColor: P.blue,
        }];

    charts.monthly = new Chart(document.getElementById('monthlyChart'), {
      type: 'line',
      data: { labels: data.monthly_labels, datasets: monthlyDatasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: isCompare } },
        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
      },
    });

    // Горизонтальный бар — воронка
    charts.funnel = new Chart(document.getElementById('funnelChart'), {
      type: 'bar',
      data: {
        labels: FUNNEL_LABELS,
        datasets: [{
          label: 'Лидов',
          data: FUNNEL_KEYS.map(k => data.funnel[k] || 0),
          backgroundColor: FUNNEL_COLORS,
          borderRadius: 4,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, ticks: { stepSize: 1 } } },
      },
    });

    // Пончик — B2B / B2G
    charts.type = new Chart(document.getElementById('typeChart'), {
      type: 'doughnut',
      data: {
        labels: ['B2B', 'B2G'],
        datasets: [{
          data: [data.b2b_count, data.b2g_count],
          backgroundColor: [P.blue, P.purple],
          hoverOffset: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } },
      },
    });

    // Пончик — каналы
    const channelEl = document.getElementById('channelChart');
    const noChannelMsg = document.getElementById('channelNoData');
    if (data.channel_labels && data.channel_labels.length > 0) {
      if (channelEl) {
        channelEl.style.display = '';
        charts.channel = new Chart(channelEl, {
          type: 'doughnut',
          data: {
            labels: data.channel_labels,
            datasets: [{
              data: data.channel_data,
              backgroundColor: PALETTE.slice(0, data.channel_labels.length),
              hoverOffset: 4,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
          },
        });
      }
      if (noChannelMsg) noChannelMsg.style.display = 'none';
    } else {
      if (channelEl) channelEl.style.display = 'none';
      if (noChannelMsg) noChannelMsg.style.display = '';
    }
  }

  // ── Обновление KPI карточек ──────────────────────────────────────────────

  function updateKPIs(metrics) {
    if (!metrics) return;
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el && val !== undefined) el.textContent = val;
    };
    set('kpi-total-leads', metrics.total_leads);
    set('kpi-converted',   metrics.converted);
    set('kpi-cr',  metrics.cr  != null ? metrics.cr  + '%' : '–');
    set('kpi-roi', metrics.roi != null ? metrics.roi + '%' : '–');
    set('kpi-cpl', metrics.cpl != null ? metrics.cpl + ' ₽' : '–');
    if (metrics.active_campaigns !== null && metrics.active_campaigns !== undefined) {
      set('kpi-active', metrics.active_campaigns);
    }
  }

  // ── Обновление DSS ───────────────────────────────────────────────────────

  function updateDSS(dssData) {
    if (!dssData) return;
    const card   = document.getElementById('dssCard');
    const badge  = document.getElementById('dssBadge');
    const icon   = document.getElementById('dssHeaderIcon');
    const items  = document.getElementById('dssItems');
    if (!card || !items) return;

    let worst = 'success';
    dssData.forEach(r => {
      if ((LEVEL_ORDER[r.level] || 0) > (LEVEL_ORDER[worst] || 0)) worst = r.level;
    });

    const [cardBorder, badgeBg, badgeText, headerIcon] = LEVEL_CARD[worst] || LEVEL_CARD.info;
    card.className = `card mb-4 border-start border-3 ${cardBorder}`;
    if (badge) {
      badge.className = `badge ${badgeBg} ${badgeText} rounded-pill`;
      badge.textContent = dssData.length;
    }
    if (icon) icon.className = `bi ${headerIcon}`;

    items.innerHTML = dssData.map(rec => {
      const [ib, it, ibg] = LEVEL_ROW[rec.level] || LEVEL_ROW.info;
      return `<div class="col-12 col-md-6">
        <div class="d-flex align-items-start gap-2 p-2 rounded border-start border-3 ${ib} ${ibg}">
          <i class="bi ${rec.icon} ${it} mt-1 flex-shrink-0"></i>
          <div>
            <div class="fw-semibold small ${it}">${rec.title}</div>
            <div class="small text-body-secondary">${rec.text}</div>
          </div>
        </div>
      </div>`;
    }).join('');

    const collapseEl = document.getElementById('dssPanel');
    if (collapseEl && window.bootstrap) {
      const bsCol = bootstrap.Collapse.getOrCreateInstance(collapseEl, { toggle: false });
      if ((LEVEL_ORDER[worst] || 0) >= 2) bsCol.show();
    }
  }

  // ── Топ кампаний: скрывать при выборе конкретной кампании ────────────────

  function updateTopSection(ids) {
    const sec = document.getElementById('topCampaignsSection');
    const title = sec && sec.previousElementSibling;
    if (sec) sec.style.display = ids.length === 1 ? 'none' : '';
    if (title && title.classList.contains('section-title')) {
      title.style.display = ids.length === 1 ? 'none' : '';
    }
  }

  // ── Excel кнопка: обновить href ──────────────────────────────────────────

  function updateExcelLink(ids) {
    const btn = document.getElementById('excelBtn');
    if (!btn) return;
    const base = btn.dataset.baseUrl;
    if (!base) return;
    btn.href = ids.length > 0 ? `${base}?campaign_ids=${ids.join(',')}` : base;
  }

  // ── Выпадающий список кампаний ───────────────────────────────────────────

  const dropBtn  = document.getElementById('campaignDropdownBtn');
  const menuEl   = document.getElementById('campaignDropdownMenu');

  function getChecked() {
    if (!menuEl) return [];
    return Array.from(menuEl.querySelectorAll('.campaign-check:checked'))
      .map(cb => parseInt(cb.value));
  }

  function getCheckedNames() {
    if (!menuEl) return [];
    return Array.from(menuEl.querySelectorAll('.campaign-check:checked'))
      .map(cb => cb.dataset.name || '');
  }

  function updateDropLabel(ids) {
    if (!dropBtn) return;
    if (ids.length === 0) {
      dropBtn.textContent = 'Все кампании';
    } else if (ids.length === 1) {
      const cb = menuEl.querySelector(`.campaign-check[value="${ids[0]}"]`);
      dropBtn.textContent = cb ? cb.dataset.name : `Кампания ${ids[0]}`;
    } else {
      dropBtn.textContent = `${ids.length} кампании выбрано`;
    }
  }

  function loadData(ids) {
    let url;
    if (ids.length === 0)    url = '/analytics/api/data';
    else if (ids.length === 1) url = `/analytics/api/data/${ids[0]}`;
    else                       url = `/analytics/api/compare?ids=${ids.join(',')}`;

    if (dropBtn) dropBtn.disabled = true;
    fetch(url)
      .then(r => r.json())
      .then(data => {
        buildCharts(data);
        updateKPIs(data.metrics);
        updateDSS(data.dss);
        updateTopSection(ids);
        updateExcelLink(ids);
      })
      .catch(() => console.error('Ошибка загрузки данных аналитики'))
      .finally(() => { if (dropBtn) dropBtn.disabled = false; });
  }

  if (menuEl) {
    menuEl.addEventListener('change', function (e) {
      if (!e.target.classList.contains('campaign-check')) return;
      selectedIds   = getChecked();
      selectedNames = getCheckedNames();
      updateDropLabel(selectedIds);
      loadData(selectedIds);
    });
  }

  const resetBtn = document.getElementById('resetCampaignFilter');
  if (resetBtn && menuEl) {
    resetBtn.addEventListener('click', function () {
      menuEl.querySelectorAll('.campaign-check').forEach(cb => { cb.checked = false; });
      selectedIds   = [];
      selectedNames = [];
      updateDropLabel([]);
      loadData([]);
      if (dropBtn && window.bootstrap) {
        bootstrap.Dropdown.getOrCreateInstance(dropBtn).hide();
      }
    });
  }

  // ── PDF экспорт через html2canvas ────────────────────────────────────────

  async function exportPDF() {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF('landscape', 'mm', 'a4');
    const W = 297, H = 210;

    // Заголовок — захватываем <h2> через html2canvas (кириллица корректно)
    const h2 = document.querySelector('h2.mb-0');
    if (h2) {
      const titleCanvas = await html2canvas(h2, { scale: 2, backgroundColor: null });
      const titleImg = titleCanvas.toDataURL('image/png');
      const th = 8;
      const tw = th * titleCanvas.width / titleCanvas.height;
      doc.addImage(titleImg, 'PNG', 10, 6, tw, th);
    }

    // Дата
    doc.setFontSize(8);
    doc.setTextColor(160);
    doc.text(new Date().toLocaleDateString('ru-RU'), W - 10, 6, { align: 'right' });

    // Подпись кампании(й) — рендерим через html2canvas для корректной кириллицы
    let pdfSubtitle = '';
    if (selectedIds.length === 1 && selectedNames.length > 0) {
      pdfSubtitle = selectedNames[0];
    } else if (selectedIds.length > 1) {
      const joined = selectedNames.join(', ');
      pdfSubtitle = joined.length > 80 ? joined.slice(0, 77) + '…' : joined;
    }
    if (pdfSubtitle) {
      const tempEl = document.createElement('span');
      tempEl.style.cssText = 'position:fixed;top:-9999px;left:0;font-size:11px;color:#6c757d;font-family:system-ui,sans-serif;white-space:nowrap;';
      tempEl.textContent = pdfSubtitle;
      document.body.appendChild(tempEl);
      try {
        const subCanvas = await html2canvas(tempEl, { scale: 2, backgroundColor: null });
        const sh = 5;
        const sw = Math.min(sh * subCanvas.width / subCanvas.height, W - 20);
        doc.addImage(subCanvas.toDataURL('image/png'), 'PNG', 10, 15, sw, sh);
      } finally {
        document.body.removeChild(tempEl);
      }
    }

    // Ячейки сетки: берём карточки целиком (заголовок + canvas)
    const cells = [
      { selector: '#monthlyChart', x: 10,  y: 20, maxW: 188, maxH: 85 },
      { selector: '#funnelChart',  x: 202, y: 20, maxW: 88,  maxH: 85 },
      { selector: '#typeChart',    x: 10,  y: 112, maxW: 88,  maxH: 90 },
      { selector: '#channelChart', x: 102, y: 112, maxW: 188, maxH: 90 },
    ];

    for (const cell of cells) {
      const canvas = document.querySelector(cell.selector);
      if (!canvas || canvas.style.display === 'none') continue;

      // Захватываем родительскую карточку (.card) для красивого PDF с заголовком
      const card = canvas.closest('.card');
      const target = card || canvas;

      let imgCanvas;
      try {
        imgCanvas = await html2canvas(target, {
          scale: 2,
          useCORS: true,
          backgroundColor: '#ffffff',
          logging: false,
        });
      } catch (_) {
        // fallback: raw canvas
        imgCanvas = canvas;
      }

      const imgData = imgCanvas.toDataURL('image/png');
      const ratio   = imgCanvas.width / imgCanvas.height;
      const drawH   = Math.min(cell.maxH, cell.maxW / ratio);
      const drawW   = drawH * ratio;
      const xOff    = cell.x + (cell.maxW - drawW) / 2;

      doc.addImage(imgData, 'PNG', xOff, cell.y, drawW, drawH);
    }

    let fileTag;
    if (selectedIds.length === 0)      fileTag = 'all';
    else if (selectedIds.length === 1) fileTag = `id${selectedIds[0]}`;
    else                               fileTag = `compare_${selectedIds.length}`;
    doc.save(`analytics_${fileTag}_${new Date().toISOString().slice(0, 10)}.pdf`);
  }

  const pdfBtn = document.getElementById('exportPdf');
  if (pdfBtn) {
    pdfBtn.addEventListener('click', () => {
      pdfBtn.disabled = true;
      exportPDF().finally(() => { pdfBtn.disabled = false; });
    });
  }

  // ── Инициализация ────────────────────────────────────────────────────────

  buildCharts(window.ANALYTICS.chartData);

})();
