(() => {
  const cache = new Map(), bundles = new Map(), editors = new Map();
  const preferenceKey = storageKey('phoca-port-plugins');
  let preferences = {}, catalog = [], frame = null, ready = Promise.resolve(), catalogLoading = false;
  let settingsGeneration = 0, settingsPending = false;
  try {
    const stored = JSON.parse(localStorage.getItem(preferenceKey) || '{}');
    if (stored && typeof stored === 'object' && !Array.isArray(stored)) preferences = stored;
  } catch {}
  function syncResult(value) {
    if (value && typeof value.then === 'function') {
      Promise.resolve(value).catch(() => {});
      throw new Error('Plugin-Frontendfunktionen muessen synchron sein.');
    }
    return value;
  }
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const severity = state => ({normal: 0, warning: 1, danger: 2}[state] || 0);
  const externalUrl = value => {
    try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password ? url.href : null; }
    catch { return null; }
  };
  const pluginPort = (port, id) => ({...port, ...(port.pluginLocations ? {pluginLocations: port.pluginLocations.filter(location => !location.ignoredPlugins?.includes(id))} : {})});
  const locationEnabled = (plugin, location) => location.plugins?.[plugin.id]?.enabled ?? !plugin.locationOptIn;
  const enabled = (plugin, port) => preferences[plugin.id] !== false && port.plugins?.[plugin.id]?.enabled !== false;
  const inWindow = (plugin, view) => !plugin.window || instant(plugin.window.from) < view.to && instant(plugin.window.to) > view.from;
  const signature = (port, plugins) => JSON.stringify([port.coordinates, port.plugins, port.pluginLocations, plugins.map(plugin => [plugin.id, plugin.window])]);

  function viewport() {
    const scroll = document.querySelector('#chart-scroll');
    const labelWidth = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--label'));
    const labelLeft = scroll.scrollLeft + labelWidth + 6, left = labelLeft + 72;
    const right = scroll.scrollLeft + scroll.clientWidth - 6;
    return {left, right, labelWidth, labelLeft, from: START + (left - labelWidth) / dayWidth * DAY, to: START + (right - labelWidth) / dayWidth * DAY};
  }

  function statusElement(label, message, view, index = 0, state = '') {
    const element = document.createElement('span');
    element.className = `port-plugin-status ${state}`;
    element.textContent = `${label}: ${message}`; element.title = element.textContent;
    Object.assign(element.style, {left: `${view.left}px`, top: `${index * 38}px`, maxWidth: `${Math.max(0, view.right - view.left)}px`});
    return element;
  }

  function locationLabel(host, track, location, view, title = '') {
    const label = document.createElement('span');
    label.className = 'port-plugin-location-label';
    Object.assign(label.style, {left: `${view.labelLeft}px`, width: '64px', top: '0px'});
    label.title = title || `${track.label}${track.unit ? ` (${track.unit})` : ''}`;
    const name = document.createElement('strong'); name.textContent = location.name;
    label.append(name); host.append(label);
  }

  function locationSettings({host, port, template, id, locations, fill, readConfig, readGlobal}) {
    host.innerHTML = template;
    const list = host.querySelector('[data-locations]'), prototype = host.querySelector('[data-location-template]');
    const globalEnabled = host.querySelector('[data-global-enabled]');
    if (globalEnabled) globalEnabled.checked = port.plugins?.[id]?.enabled !== false;
    const dirty = () => host.dispatchEvent(new Event('input', {bubbles: true}));
    function add(location = null) {
      const row = prototype.content.firstElementChild.cloneNode(true);
      row.dataset.locationId = location?.plugin === id ? location.id : `location-${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`;
      row.pluginOriginal = location;
      for (const [field, value] of Object.entries({name: location?.name || '', url: location?.url || '', latitude: location?.coordinates?.latitude ?? '', longitude: location?.coordinates?.longitude ?? ''})) row.querySelector(`[data-field="${field}"]`).value = value;
      row.querySelector('[data-enabled]').checked = location?.plugins?.[id]?.enabled !== false;
      if (fill) syncResult(fill(row, location));
      list.append(row); icons();
    }
    for (const location of locations) add(location);
    host.addEventListener('click', event => {
      if (event.target.closest('[data-add]')) { add(); dirty(); }
      const remove = event.target.closest('[data-remove]');
      if (remove) { remove.closest('[data-location-id]').remove(); dirty(); }
    });
    return {read() {
      let settings = {...(port.plugins?.[id] || {})};
      if (globalEnabled) settings.enabled = globalEnabled.checked;
      if (readGlobal) settings = syncResult(readGlobal(settings));
      return {settings, locations: [...list.querySelectorAll('[data-location-id]')].map(row => {
        const previous = row.pluginOriginal || {}, config = {...(previous.plugins?.[id] || {})};
        const field = name => row.querySelector(`[data-field="${name}"]`).value;
        if (field('latitude') === '' || field('longitude') === '') throw new Error('Breiten- und Laengengrad fuer jeden Standort angeben.');
        const local = readConfig ? syncResult(readConfig(row, config)) : config;
        return {...previous, id: row.dataset.locationId, plugin: id, ignoredPlugins: [], name: field('name').trim(), url: field('url').trim(),
          coordinates: {latitude: Number(field('latitude')), longitude: Number(field('longitude'))},
          plugins: {[id]: {...local, enabled: row.querySelector('[data-enabled]').checked}}};
      })};
    }};
  }

  function api() {
    return {instant, iso, shortDate, finite, severity, externalUrl, statusElement, locationLabel, locationSettings,
      START, END, DAY, HOUR, dayWidth, rowHeight: 38, now: new Date().toISOString(), timeBasis: 'UTC', icons};
  }

  async function mountSettings(container, port) {
    const generation = ++settingsGeneration;
    settingsPending = true; editors.clear(); container.replaceChildren();
    if (port === null) { settingsPending = false; return; }
    await ready;
    if (generation !== settingsGeneration) return;
    for (const plugin of catalog) {
      const host = document.createElement('div'); host.dataset.pluginPackage = plugin.id;
      container.append(host);
      try {
        const bundle = bundles.get(plugin.id);
        if (bundle?.error) throw bundle.error;
        const editor = syncResult(bundle.module.mountSettings({host, port: pluginPort(port, plugin.id), template: bundle.template, api: api(), metadata: plugin}));
        if (!editor || typeof editor.read !== 'function') throw new Error('Einstellungsvertrag ungueltig.');
        editors.set(plugin.id, editor);
      } catch {
        host.textContent = `${plugin.label}: Einstellungen derzeit nicht verfuegbar. Gespeicherte Daten bleiben erhalten.`;
      }
    }
    settingsPending = false; icons();
  }

  function readSettings(original) {
    if (settingsPending) throw new Error('Plugin-Einstellungen werden noch geladen.');
    const plugins = {...(original?.plugins || {})};
    if (!editors.size) return {plugins, pluginLocations: original?.pluginLocations};
    const locations = (original?.pluginLocations || []).flatMap(location => {
      if (location.plugin) return editors.has(location.plugin) ? [] : [location];
      const unavailable = Object.keys(location.plugins || {}).some(id => !editors.has(id));
      return unavailable ? [{...location, ignoredPlugins: [...new Set([...(location.ignoredPlugins || []), ...editors.keys()])]}] : [];
    });
    for (const [id, editor] of editors) {
      const result = syncResult(editor.read());
      if (!result || !Array.isArray(result.locations) || !result.settings || result.locations.some(location => location.plugin !== id)) throw new Error('Plugin-Konfiguration ungueltig.');
      plugins[id] = result.settings; locations.push(...result.locations);
    }
    return {plugins, pluginLocations: locations};
  }

  async function loadPort(port, plugins, key, view) {
    const previous = cache.get(port.id);
    if (previous?.key === key && (previous.pending || previous.expires > Date.now())) return;
    const windows = plugins.map(plugin => plugin.window || {from: iso(Math.floor(view.from / DAY) * DAY - DAY), to: iso(Math.ceil(view.to / DAY) * DAY + DAY)});
    const entry = {key, pending: true, tracks: [], expires: 0}; cache.set(port.id, entry);
    if (cache.size > 100) cache.delete(cache.keys().next().value);
    try {
      const query = new URLSearchParams({start: windows.map(window => window.from).sort()[0], end: windows.map(window => window.to).sort().at(-1), plugins: plugins.map(plugin => plugin.id).join(',')});
      const response = await fetch(`/api/ports/${encodeURIComponent(port.id)}/plugins?${query}`), result = await response.json();
      if (!response.ok || result.schemaVersion !== 1 || result.portId !== port.id || !Array.isArray(result.tracks)) throw new Error();
      entry.tracks = result.tracks;
      const lifetime = entry.tracks.some(track => ['error', 'stale'].includes(track.status)) ? 300000 : 3600000;
      entry.expires = Date.now() + Math.min(lifetime, ...entry.tracks.map(track => track.refreshAfterSeconds).filter(seconds => finite(seconds) && seconds > 0).map(seconds => seconds * 1000));
    } catch {
      entry.tracks = plugins.map(plugin => ({...plugin, status: 'error', message: 'Daten nicht verfuegbar.', samples: []})); entry.expires = Date.now() + 300000;
    } finally {
      entry.pending = false;
      setTimeout(() => { if (cache.get(port.id) === entry) schedule(); }, Math.max(1000, entry.expires - Date.now() + 10)); schedule();
    }
  }

  function draw() {
    frame = null;
    if (typeof saved === 'undefined' || !saved?.ports) return;
    let layoutChanged = false;
    for (const host of document.querySelectorAll('[data-port-plugins]')) {
      host.replaceChildren();
      const port = saved.ports.find(item => item.id === host.dataset.portPlugins);
      if (!port) continue;
      const lanes = [];
      for (const plugin of catalog.filter(plugin => enabled(plugin, port))) {
        const bundle = bundles.get(plugin.id);
        try {
          const localPort = pluginPort(port, plugin.id);
          const locations = bundle?.module?.locations ? syncResult(bundle.module.locations(localPort)) : (localPort.pluginLocations || []).filter(location => location.plugin === plugin.id);
          for (const location of locations.filter(location => locationEnabled(plugin, location))) lanes.push({plugin, location});
        } catch { console.warn(`Plugin ${plugin.id}: Standortliste nicht verfuegbar.`); }
      }
      const height = lanes.length ? `${lanes.length * 38}px` : '';
      if (host.parentElement.style.minHeight !== height) layoutChanged = true;
      host.parentElement.style.minHeight = height; host.style.top = '';
      const view = viewport(); if (view.right <= view.left || !lanes.length) continue;
      const active = catalog.filter(plugin => lanes.some(lane => lane.plugin.id === plugin.id) && inWindow(plugin, view) && !bundles.get(plugin.id)?.error);
      const key = signature(port, active) + (active.some(plugin => !plugin.window) ? `:${iso(view.from).slice(0, 10)}:${iso(view.to).slice(0, 10)}` : '');
      let entry = cache.get(port.id);
      if (active.length && (entry?.key !== key || entry.expires <= Date.now()) && !entry?.pending) { loadPort(port, active, key, view); entry = cache.get(port.id); }
      for (const [index, {plugin, location}] of lanes.entries()) {
        const row = document.createElement('div'); row.dataset.pluginPackage = plugin.id;
        Object.assign(row.style, {position: 'absolute', left: '0px', top: `${index * 38}px`, width: '100%', height: '38px', overflow: 'hidden', pointerEvents: 'none'}); host.append(row);
        const track = entry?.key === key ? entry.tracks.find(item => item.id === plugin.id && (item.locationId || 'terminal') === location.id) : null;
        const current = track || {...plugin, status: inWindow(plugin, view) ? 'loading' : 'out-of-range', message: inWindow(plugin, view) ? 'Wird geladen' : 'Ausserhalb des Datenzeitraums', samples: []};
        try {
          const bundle = bundles.get(plugin.id); if (!bundle?.module || bundle.error) throw new Error();
          syncResult(bundle.module.render({host: row, track: {...current, label: `${plugin.label} / ${location.name}`}, view, location, port, config: location.plugins?.[plugin.id] || {}, api: api()}));
        } catch { row.replaceChildren(statusElement(plugin.label, 'Plugin-Darstellung nicht verfuegbar.', view)); }
      }
    }
    if (layoutChanged) renderConnections(); icons();
  }

  function schedule() { if (frame === null) frame = requestAnimationFrame(draw); }
  function setPreference(id, value) {
    preferences[id] = value;
    try { localStorage.setItem(preferenceKey, JSON.stringify(preferences)); } catch {}
    renderOptions(); schedule();
  }

  function renderOptions() {
    const container = document.querySelector('#port-plugin-options'), sources = document.querySelector('#port-plugin-sources'), toolbar = document.querySelector('#plugin-toolbar');
    container.replaceChildren(); sources.replaceChildren(); toolbar.replaceChildren();
    for (const plugin of catalog) {
      const label = document.createElement('label'), checkbox = document.createElement('input');
      checkbox.type = 'checkbox'; checkbox.checked = preferences[plugin.id] !== false;
      checkbox.addEventListener('change', () => setPreference(plugin.id, checkbox.checked));
      label.append(checkbox, document.createTextNode(`${plugin.label}${plugin.unit ? ` (${plugin.unit})` : ''}`)); container.append(label);
      if (externalUrl(plugin.source?.url)) {
        const link = document.createElement('a'); link.href = plugin.source.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = plugin.source.attribution || plugin.source.name; sources.append(link);
      }
      if (plugin.quickToggle) {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'button port-plugin-toggle'; button.dataset.pluginToggle = plugin.id;
        button.textContent = plugin.label; button.setAttribute('aria-pressed', String(preferences[plugin.id] !== false)); button.title = `${plugin.label} ein-/ausblenden`;
        if (plugin.icon) { const icon = document.createElement('i'); icon.dataset.lucide = plugin.icon; icon.setAttribute('aria-hidden', 'true'); button.prepend(icon); }
        button.addEventListener('click', () => setPreference(plugin.id, preferences[plugin.id] === false)); toolbar.append(button);
      }
    }
    icons();
  }

  async function loadBundle(plugin) {
    try {
      const response = await fetch(plugin.assets.settings); if (!response.ok) throw new Error();
      const template = await response.text(), module = await import(plugin.assets.frontend);
      if (typeof module.render !== 'function' || typeof module.mountSettings !== 'function') throw new Error('Plugin-Schnittstelle ungueltig.');
      if (!document.querySelector(`link[data-plugin-style="${plugin.id}"]`)) {
        const style = document.createElement('link'); style.rel = 'stylesheet'; style.href = plugin.assets.style; style.dataset.pluginStyle = plugin.id;
        await new Promise((resolve, reject) => { style.onload = resolve; style.onerror = reject; document.head.append(style); });
      }
      bundles.set(plugin.id, {module, template});
    } catch (error) { bundles.set(plugin.id, {error}); console.warn(`Plugin ${plugin.id}: Frontend nicht geladen.`); }
  }

  function loadCatalog() {
    if (catalogLoading) return ready;
    catalogLoading = true;
    ready = (async () => {
      try {
        const response = await fetch('/api/port-plugins'), result = await response.json();
        if (!response.ok || result.schemaVersion !== 1 || !Array.isArray(result.plugins)) throw new Error();
        catalog = result.plugins;
        await Promise.all(catalog.map(plugin => bundles.has(plugin.id) ? Promise.resolve() : loadBundle(plugin)));
        renderOptions(); schedule();
      } catch { document.querySelector('#port-plugin-options').textContent = 'Plugin-Liste derzeit nicht verfuegbar.'; }
      finally { catalogLoading = false; }
    })();
    ready.then(() => document.dispatchEvent(new Event('phoca-plugins-ready')));
    return ready;
  }

  globalThis.PortPlugins = {schedule, refresh: draw, mountSettings, readSettings};
  document.querySelector('#chart-scroll').addEventListener('scroll', schedule, {passive: true});
  globalThis.addEventListener('resize', schedule); globalThis.addEventListener('focus', schedule);
  setInterval(loadCatalog, 3600000); loadCatalog();
})();