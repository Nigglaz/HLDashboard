(() => {
  const cache = new Map();
  const preferenceKey = storageKey('phoca-port-plugins');
  let preferences = {}, catalog = [], frame = null, catalogLoading = false;
  try {
    const stored = JSON.parse(localStorage.getItem(preferenceKey) || '{}');
    if (stored && typeof stored === 'object' && !Array.isArray(stored)) preferences = stored;
  } catch {}

  const enabled = (plugin, port) => preferences[plugin.id] !== false && port.plugins?.[plugin.id]?.enabled !== false;
  const finite = (value) => typeof value === 'number' && Number.isFinite(value);
  const severity = (state) => ({normal: 0, warning: 1, danger: 2}[state] || 0);
  const signature = (port, plugins) => JSON.stringify([port.coordinates, port.plugins, plugins.map((plugin) => [plugin.id, plugin.window])]);

  function viewport(host) {
    const scroll = document.querySelector('#chart-scroll');
    const controls = host.parentElement.querySelector('.port-heading-content');
    const labelWidth = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--label'));
    const left = scroll.scrollLeft + (matchMedia('(max-width:760px)').matches ? labelWidth : controls.getBoundingClientRect().width) + 6;
    const right = scroll.scrollLeft + scroll.clientWidth - 6;
    return {left, right, labelWidth,
      from: START + (left - labelWidth) / dayWidth * DAY,
      to: START + (right - labelWidth) / dayWidth * DAY};
  }

  function inWindow(plugin, view) {
    if (!plugin.window) return true;
    return instant(plugin.window.from) < view.to && instant(plugin.window.to) > view.from;
  }

  async function loadPort(port, plugins, key, view) {
    const previous = cache.get(port.id);
    if (previous?.key === key && (previous.pending || previous.expires > Date.now())) return;
    const windows = plugins.map((plugin) => plugin.window || {from: iso(Math.floor(view.from / DAY) * DAY - DAY), to: iso(Math.ceil(view.to / DAY) * DAY + DAY)});
    const from = windows.map((window) => window.from).sort()[0];
    const to = windows.map((window) => window.to).sort().at(-1);
    const entry = {key, pending: true, tracks: [], expires: 0};
    cache.set(port.id, entry);
    if (cache.size > 100) cache.delete(cache.keys().next().value);
    try {
      const query = new URLSearchParams({start: from, end: to, plugins: plugins.map((plugin) => plugin.id).join(',')});
      const response = await fetch(`/api/ports/${encodeURIComponent(port.id)}/plugins?${query}`);
      const result = await response.json();
      if (!response.ok || result.schemaVersion !== 1 || result.portId !== port.id || !Array.isArray(result.tracks)) throw new Error('Plugin-Daten nicht verfuegbar.');
      entry.tracks = result.tracks;
      const defaultLifetime = entry.tracks.some((track) => ['error', 'stale'].includes(track.status)) ? 300000 : 3600000;
      const lifetimes = entry.tracks.map((track) => track.refreshAfterSeconds).filter((seconds) => finite(seconds) && seconds > 0).map((seconds) => seconds * 1000);
      entry.expires = Date.now() + Math.min(defaultLifetime, ...lifetimes);
    } catch {
      entry.tracks = plugins.map((plugin) => ({...plugin, status: 'error', message: 'Daten nicht verfuegbar.', samples: []}));
      entry.expires = Date.now() + 300000;
    } finally {
      entry.pending = false;
      setTimeout(() => { if (cache.get(port.id) === entry) schedule(); }, Math.max(1000, entry.expires - Date.now() + 10));
      schedule();
    }
  }

  function statusElement(label, message, view, index, state = '') {
    const element = document.createElement('span');
    element.className = `port-plugin-status ${state}`;
    element.textContent = `${label}: ${message}`;
    element.title = element.textContent;
    element.style.left = `${view.left}px`;
    element.style.top = `${index * 38}px`;
    element.style.maxWidth = `${Math.max(0, view.right - view.left)}px`;
    return element;
  }

  function renderTrack(host, track, view, index) {
    if (!['directional', 'value'].includes(track.presentation)) return;
    const basePixels = dayWidth * (track.intervalMinutes || 180) / 1440;
    const stride = 2 ** Math.max(0, Math.ceil(Math.log2(37 / basePixels)));
    const displayInterval = (track.intervalMinutes || 180) * 60000 * stride;
    const valueRight = track.status === 'stale' ? Math.max(view.left, view.right - 150) : view.right;
    const samples = new Map();
    for (const sample of track.samples || []) {
      const time = instant(sample.time);
      if (!Number.isFinite(time) || !finite(sample.value) || time % displayInterval !== 0) continue;
      const left = view.labelWidth + (time - START) / DAY * dayWidth;
      if (left < view.left + 16 || left > valueRight - 16) continue;
      samples.set(time, {sample, left});
    }
    const fragment = document.createDocumentFragment();
    for (const period of track.periods || []) {
      const start = instant(period.start), end = instant(period.end);
      if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start || !severity(period.state)) continue;
      const left = Math.max(view.left, view.labelWidth + (Math.max(start, START) - START) / DAY * dayWidth);
      const right = Math.min(valueRight, view.labelWidth + (Math.min(end, END) - START) / DAY * dayWidth);
      if (right <= left) continue;
      const band = document.createElement('span');
      band.className = `port-plugin-period plugin-${period.state}`;
      band.style.left = `${left}px`;
      band.style.width = `${right - left}px`;
      band.style.top = `${index * 38}px`;
      band.dataset.start = period.start;
      band.dataset.end = period.end;
      band.title = `${track.label} / ${shortDate(start)} - ${shortDate(end)} UTC\n${period.label || 'Kritischer Zeitraum'}${track.status === 'stale' ? '\nVeralteter Datenstand' : ''}`;
      band.setAttribute('role', 'img');
      band.setAttribute('aria-label', band.title);
      fragment.append(band);
    }
    for (const {sample, left} of [...samples.values()].sort((first, second) => first.left - second.left)) {
      const element = document.createElement('span');
      element.className = 'port-plugin-value';
      if (severity(sample.state)) element.classList.add(`plugin-${sample.state}`);
      element.style.left = `${left - 16}px`;
      element.style.top = `${index * 38 + 2}px`;
      const stamp = `${shortDate(instant(sample.time))} UTC`;
      element.title = `${track.label} / ${stamp}\n${sample.label || `${sample.value} ${sample.unit || track.unit || ''}`}\n${track.source?.attribution || track.source?.name || ''}${track.fetchedAt ? `\nStand: ${track.fetchedAt}` : ''}${track.status === 'stale' ? '\nVeralteter Datenstand' : ''}`;
      element.setAttribute('aria-label', element.title);
      element.setAttribute('role', 'img');
      element.dataset.time = sample.time;
      element.dataset.intervalHours = displayInterval / HOUR;
      const number = document.createElement('strong');
      number.textContent = track.presentation === 'directional' && sample.value > 10 ? Math.round(sample.value) : Number(sample.value.toFixed(1));
      element.append(number);
      if (track.presentation === 'directional' && finite(sample.rotationDegrees)) {
        element.classList.add('port-plugin-directional');
        const pointer = document.createElement('span');
        pointer.className = 'port-plugin-pointer';
        pointer.style.transform = `rotate(${sample.rotationDegrees}deg)`;
        pointer.innerHTML = '<i data-lucide="chevron-up" aria-hidden="true"></i>';
        element.append(pointer);
      } else {
        const unit = document.createElement('small');
        unit.textContent = sample.unit || track.unit || '';
        element.append(unit);
      }
      fragment.append(element);
    }
    host.append(fragment);
    if (track.status === 'stale') {
      const status = statusElement(track.label, 'veralteter Stand', view, index, 'plugin-stale');
      status.style.left = `${Math.max(view.left, view.right - 150)}px`;
      host.append(status);
    } else if (!samples.size) {
      host.append(statusElement(track.label, track.message || 'Keine Werte im sichtbaren Zeitraum', view, index));
    }
  }

  function draw() {
    frame = null;
    if (typeof saved === 'undefined' || !saved?.ports) return;
    let layoutChanged = false;
    for (const host of document.querySelectorAll('[data-port-plugins]')) {
      host.replaceChildren();
      const port = saved.ports.find((item) => item.id === host.dataset.portPlugins);
      if (!port) continue;
      const plugins = catalog.filter((plugin) => enabled(plugin, port));
      const narrow = matchMedia('(max-width:760px)').matches;
      const height = plugins.length ? `${plugins.length * 38 + (narrow ? 35 : 0)}px` : '';
      if (host.parentElement.style.minHeight !== height) layoutChanged = true;
      host.parentElement.style.minHeight = height;
      host.style.top = plugins.length && narrow ? '35px' : '';
      if (!plugins.length) continue;
      const view = viewport(host);
      if (view.right <= view.left) continue;
      const active = plugins.filter((plugin) => inWindow(plugin, view));
      const key = signature(port, active) + (active.some((plugin) => !plugin.window) ? `:${iso(view.from).slice(0, 10)}:${iso(view.to).slice(0, 10)}` : '');
      let entry = cache.get(port.id);
      if (active.length && (entry?.key !== key || entry.expires <= Date.now()) && !entry?.pending) {
        loadPort(port, active, key, view);
        entry = cache.get(port.id);
      }
      for (const [index, plugin] of plugins.entries()) {
        if (!inWindow(plugin, view)) { host.append(statusElement(plugin.label, 'Ausserhalb des Datenzeitraums', view, index)); continue; }
        const track = entry?.key === key ? entry.tracks.find((item) => item.id === plugin.id) : null;
        if (!track) { host.append(statusElement(plugin.label, 'Wird geladen', view, index)); continue; }
        if (!['ready', 'stale'].includes(track.status)) { host.append(statusElement(plugin.label, track.message || 'Keine Daten', view, index)); continue; }
        renderTrack(host, track, view, index);
      }
    }
    if (layoutChanged) renderConnections();
    if (globalThis.lucide) globalThis.lucide.createIcons();
  }

  function schedule() {
    if (frame === null) frame = requestAnimationFrame(draw);
  }

  function renderOptions() {
    const container = document.querySelector('#port-plugin-options');
    const sources = document.querySelector('#port-plugin-sources');
    container.replaceChildren(); sources.replaceChildren();
    for (const plugin of catalog) {
      const label = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox'; checkbox.checked = preferences[plugin.id] !== false;
      checkbox.addEventListener('change', () => {
        setPreference(plugin.id, checkbox.checked);
      });
      label.append(checkbox, document.createTextNode(`${plugin.label}${plugin.unit ? ` (${plugin.unit})` : ''}`));
      container.append(label);
      if (plugin.source?.url?.startsWith('https://')) {
        const link = document.createElement('a');
        link.href = plugin.source.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
        link.textContent = plugin.source.attribution || plugin.source.name;
        sources.append(link);
      }
    }
    const toggle = document.querySelector('#weather-toggle');
    const weatherEnabled = preferences.weather !== false;
    toggle.disabled = !catalog.some((plugin) => plugin.id === 'weather');
    toggle.setAttribute('aria-pressed', String(weatherEnabled));
    toggle.title = weatherEnabled ? 'Windanzeige ausblenden' : 'Windanzeige einblenden';
  }

  function setPreference(identity, value) {
    preferences[identity] = value;
    try { localStorage.setItem(preferenceKey, JSON.stringify(preferences)); } catch {}
    renderOptions(); schedule();
  }

  async function loadCatalog() {
    if (catalogLoading) return;
    catalogLoading = true;
    try {
      const response = await fetch('/api/port-plugins');
      const result = await response.json();
      if (!response.ok || result.schemaVersion !== 1 || !Array.isArray(result.plugins)) throw new Error();
      catalog = result.plugins;
      renderOptions(); schedule();
    } catch {
      document.querySelector('#port-plugin-options').textContent = 'Plugin-Liste derzeit nicht verfuegbar.';
    } finally { catalogLoading = false; }
  }

  globalThis.PortPlugins = {schedule};
  document.querySelector('#weather-toggle').addEventListener('click', () => setPreference('weather', preferences.weather === false));
  document.querySelector('#chart-scroll').addEventListener('scroll', schedule, {passive: true});
  globalThis.addEventListener('resize', schedule);
  globalThis.addEventListener('focus', schedule);
  setInterval(() => { loadCatalog(); schedule(); }, 3600000);
  loadCatalog();
})();