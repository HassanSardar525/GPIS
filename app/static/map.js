/**
 * GPIS Interactive District Map Module (app/static/map.js)
 * Pure Vanilla ES6 JavaScript — Isolated, self-contained component
 */
(function initGPISMapModule() {
  const DEFAULT_VIEWBOX = { x: 80, y: 20, w: 640, h: 700 };
  let currentViewBox = { ...DEFAULT_VIEWBOX };
  let animFrameId = null;
  let activeSlug = null;

  function getElements() {
    return {
      container: document.getElementById('gpis-map-container'),
      svg: document.getElementById('gpis-pakistan-map'),
      districtsGroup: document.getElementById('map-districts-group'),
      labelsGroup: document.getElementById('map-labels-group'),
      resetBtn: document.getElementById('map-reset-btn'),
      statusPill: document.getElementById('map-status-pill'),
      statusText: document.getElementById('map-status-text'),
      tooltip: document.getElementById('map-floating-tooltip'),
      tooltipName: document.getElementById('tooltip-district-name'),
      tooltipScore: document.getElementById('tooltip-district-score'),
      tooltipBadge: document.getElementById('tooltip-district-badge'),
      tooltipMeta: document.getElementById('tooltip-district-meta'),
      selectEl: document.getElementById('district-select'),
    };
  }

  /**
   * Smoothly animates the SVG viewBox using cubic-out easing
   */
  function animateViewBox(targetBox, duration = 480) {
    const { svg } = getElements();
    if (!svg) return;
    if (animFrameId) cancelAnimationFrame(animFrameId);

    const startBox = { ...currentViewBox };
    const startTime = performance.now();

    function easeOutCubic(t) {
      return 1 - Math.pow(1 - t, 3);
    }

    function step(now) {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);
      const eased = easeOutCubic(progress);

      currentViewBox.x = startBox.x + (targetBox.x - startBox.x) * eased;
      currentViewBox.y = startBox.y + (targetBox.y - startBox.y) * eased;
      currentViewBox.w = startBox.w + (targetBox.w - startBox.w) * eased;
      currentViewBox.h = startBox.h + (targetBox.h - startBox.h) * eased;

      svg.setAttribute(
        'viewBox',
        `${currentViewBox.x.toFixed(2)} ${currentViewBox.y.toFixed(2)} ${currentViewBox.w.toFixed(2)} ${currentViewBox.h.toFixed(2)}`
      );

    if (progress < 1) {
        animFrameId = requestAnimationFrame(step);
      } else {
        animFrameId = null;
      }
    }

    animFrameId = requestAnimationFrame(step);
  }

  /**
   * Zooms into a specific district path's bounding box with comfortable padding
   */
  function zoomToDistrictPath(pathEl) {
    if (!pathEl) return;
    try {
      const bbox = pathEl.getBBox();
      const padX = Math.max(bbox.width * 0.85, 65);
      const padY = Math.max(bbox.height * 0.85, 65);

      let targetW = Math.max(bbox.width + padX * 2, 190);
      let targetH = Math.max(bbox.height + padY * 2, 210);

      // Maintain aspect ratio close to DEFAULT_VIEWBOX (640 / 700)
      const targetRatio = DEFAULT_VIEWBOX.w / DEFAULT_VIEWBOX.h;
      if (targetW / targetH > targetRatio) {
        targetH = targetW / targetRatio;
      } else {
        targetW = targetH * targetRatio;
      }

      const cx = bbox.x + bbox.width / 2;
      const cy = bbox.y + bbox.height / 2;

      animateViewBox({
        x: cx - targetW / 2,
        y: cy - targetH / 2,
        w: targetW,
        h: targetH,
      });
    } catch {
      /* getBBox may fail if SVG is unattached */
    }
  }

  /**
   * Resets map zoom and clears selection dimming
   */
  function resetMapView(clearSelection = false) {
    const { container, districtsGroup, labelsGroup, resetBtn, statusPill, statusText } = getElements();
    animateViewBox(DEFAULT_VIEWBOX, 440);
    if (resetBtn) resetBtn.classList.add('is-hidden');
    if (statusPill) statusPill.classList.remove('is-zoomed');

    if (clearSelection) {
      activeSlug = null;
      if (container) container.classList.remove('has-selection');
      if (districtsGroup) {
        districtsGroup.querySelectorAll('.district-path.is-active').forEach((el) => {
          el.classList.remove('is-active');
        });
      }
      if (labelsGroup) {
        labelsGroup.querySelectorAll('.district-label-group.is-active-label').forEach((el) => {
          el.classList.remove('is-active-label');
        });
      }
      if (statusText) {
        statusText.textContent = 'All 36 Districts · Click a district to inspect';
      }
    }
  }

  /**
   * Highlights a district on the map and zooms to its bounding box.
   * Exposed globally as window.highlightDistrictOnMap(slug, options).
   */
  function highlightDistrictOnMap(slug, options = { zoom: true }) {
    const { container, districtsGroup, labelsGroup, resetBtn, statusPill, statusText } = getElements();
    if (!districtsGroup) return;

    if (!slug || slug === 'all' || slug === '') {
      resetMapView(true);
      return;
    }

    const normalizedSlug = String(slug).trim().toLowerCase();
    const targetPath = districtsGroup.querySelector(`.district-path[data-district="${normalizedSlug}"]`);
    if (!targetPath) {
      return;
    }

    activeSlug = normalizedSlug;
    if (container) container.classList.add('has-selection');

    // Update active class on paths
    districtsGroup.querySelectorAll('.district-path').forEach((el) => {
      el.classList.toggle('is-active', el === targetPath);
    });

    // Bring active path to front of SVG stacking order so its gold border is never occluded
    districtsGroup.appendChild(targetPath);

    // Highlight matching label group
    if (labelsGroup) {
      labelsGroup.querySelectorAll('.district-label-group').forEach((grp) => {
        const isMatch = grp.getAttribute('data-for') === normalizedSlug;
        grp.classList.toggle('is-active-label', isMatch);
        if (isMatch) labelsGroup.appendChild(grp);
      });
    }

    const dName = targetPath.getAttribute('data-name') || normalizedSlug;
    const dStatus = targetPath.getAttribute('data-status') || '';
    if (statusText) {
      statusText.textContent = `${dName} · ${dStatus}`;
    }
    if (statusPill) statusPill.classList.add('is-zoomed');
    if (resetBtn) resetBtn.classList.remove('is-hidden');

    if (options.zoom !== false) {
      zoomToDistrictPath(targetPath);
    }
  }

  /**
   * Floating HTML tooltip with viewport boundary protection
   */
  function showTooltip(pathEl, clientX, clientY) {
    const { tooltip, tooltipName, tooltipScore, tooltipBadge, tooltipMeta } = getElements();
    if (!tooltip || !pathEl) return;

    const name = pathEl.getAttribute('data-name') || '';
    const status = pathEl.getAttribute('data-status') || '';
    const division = pathEl.getAttribute('data-division') || '';
    const pop = pathEl.getAttribute('data-pop') || '';
    const score = pathEl.getAttribute('data-score');
    const isScored = pathEl.classList.contains('is-scored');

    if (tooltipName) tooltipName.textContent = name;
    if (tooltipScore) {
      if (score) {
        tooltipScore.textContent = `GPIS ${score}`;
        tooltipScore.style.display = 'inline-block';
      } else {
        tooltipScore.style.display = 'none';
      }
    }

    if (tooltipBadge) {
      tooltipBadge.textContent = status;
      tooltipBadge.className = 'map-tooltip-badge ' + (isScored ? 'badge-scored' : 'badge-factual');
    }
    if (tooltipMeta) {
      tooltipMeta.textContent = `${division} Division · Census Pop: ${pop}`;
    }

    tooltip.classList.add('is-visible');
    tooltip.setAttribute('aria-hidden', 'false');

    positionTooltip(clientX, clientY);
  }

  function positionTooltip(clientX, clientY) {
    const { tooltip } = getElements();
    if (!tooltip) return;
    const offset = 16;
    const rect = tooltip.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let left = clientX + offset;
    let top = clientY + offset;

    // Boundary checks
    if (left + rect.width + 12 > vw) {
      left = clientX - rect.width - offset;
    }
    if (left < 12) {
      left = 12;
    }
    if (top + rect.height + 12 > vh) {
      top = clientY - rect.height - offset;
    }
    if (top < 12) {
      top = 12;
    }

    tooltip.style.transform = `translate3d(${Math.round(left)}px, ${Math.round(top)}px, 0)`;
  }

  function hideTooltip() {
    const { tooltip } = getElements();
    if (!tooltip) return;
    tooltip.classList.remove('is-visible');
    tooltip.setAttribute('aria-hidden', 'true');
  }

  /**
   * Handles selecting a district from the map and syncing with dropdown & loadDistrict(slug)
   */
  function selectDistrictFromMap(slug) {
    if (!slug) return;
    highlightDistrictOnMap(slug, { zoom: true });

    const { selectEl } = getElements();

    // 1. Update #district-select and dispatch change event
    if (selectEl && selectEl.value !== slug) {
      selectEl.value = slug;
      selectEl.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // The select change handler already loads changed districts.
    else if (typeof window.loadDistrict === 'function') {
      window.loadDistrict(slug).catch?.(console.error);
    }
  }

  function setupEventListeners() {
    const { svg, districtsGroup, resetBtn, selectEl } = getElements();
    if (!svg || !districtsGroup) return;

    // Hover tooltip
    districtsGroup.addEventListener('pointermove', (e) => {
      const pathEl = e.target.closest('.district-path');
      if (!pathEl) {
        hideTooltip();
        return;
      }
      showTooltip(pathEl, e.clientX, e.clientY);
    });

    districtsGroup.addEventListener('pointerleave', () => {
      hideTooltip();
    });

    // Click to select
    districtsGroup.addEventListener('click', (e) => {
      const pathEl = e.target.closest('.district-path');
      if (!pathEl) return;
      const slug = pathEl.getAttribute('data-district');
      selectDistrictFromMap(slug);
    });

    // Touch support for mobile tap
    districtsGroup.addEventListener('touchstart', (e) => {
      const pathEl = e.target.closest('.district-path');
      if (!pathEl || !e.touches[0]) return;
      const touch = e.touches[0];
      showTooltip(pathEl, touch.clientX, touch.clientY);
    }, { passive: true });

    // Keyboard navigation
    districtsGroup.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        const pathEl = e.target.closest('.district-path');
        if (!pathEl) return;
        e.preventDefault();
        selectDistrictFromMap(pathEl.getAttribute('data-district'));
      }
    });

    // Background click resets view
    svg.addEventListener('click', (e) => {
      if (e.target === svg || e.target.classList.contains('province-context-path')) {
        resetMapView(false);
      }
    });

    // Reset button
    if (resetBtn) {
      resetBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        resetMapView(false);
        hideTooltip();
      });
    }

    // Two-way sync: listen to #district-select changes
    if (selectEl) {
      selectEl.addEventListener('change', (e) => {
        const newSlug = e.target.value;
        if (newSlug && newSlug !== activeSlug) {
          highlightDistrictOnMap(newSlug, { zoom: true });
        }
      });
    }
  }

  // Expose public API globally
  window.highlightDistrictOnMap = highlightDistrictOnMap;
  window.updateDistrictMapData = (districts, populations = []) => {
    const bySlug = new Map(districts.map(d => [d.slug, d]));
    const population = new Map(populations.map(d => [d.slug, d.value]));
    document.querySelectorAll('.district-path').forEach(path => {
      const d = bySlug.get(path.dataset.district);
      const score = d?.scores?.overall;
      path.classList.toggle('is-scored', score != null);
      path.dataset.status = score != null ? 'Performance profile' : 'Official facts; no score';
      if (score != null) path.dataset.score = String(score); else delete path.dataset.score;
      path.dataset.pop = population.has(path.dataset.district) ? new Intl.NumberFormat('en-PK').format(population.get(path.dataset.district)) : 'Loading';
      path.setAttribute('aria-label', `${d?.name || path.dataset.name}: ${path.dataset.status}`);
    });
    document.querySelectorAll('.district-label-group').forEach(group => {
      const scored = bySlug.get(group.dataset.for)?.scores?.overall != null;
      group.querySelector('.district-map-label')?.classList.toggle('is-scored-label', scored);
    });
  };
  window.resetDistrictMapView = () => resetMapView(true);

  function start() {
    setupEventListeners();
    const { selectEl } = getElements();
    const initialSlug =
      (window.state && window.state.district && window.state.district.slug) ||
      (selectEl && selectEl.value);
    if (initialSlug) {
      highlightDistrictOnMap(initialSlug, { zoom: false });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
