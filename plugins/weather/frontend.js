export function locations(port) {
  const all = port.pluginLocations || (port.coordinates ? [{id: 'terminal', name: port.name, coordinates: port.coordinates, plugins: {}}] : []);
  return all.filter(location => location.plugin === 'weather' || !location.plugin && (location.plugins?.weather?.enabled !== false || !Object.entries(location.plugins || {}).some(([id, settings]) => id !== 'weather' && settings.enabled === true)));
}

export function mountSettings(context) {
  return context.api.locationSettings({...context, id: 'weather', locations: locations(context.port),
    fill(row, location) {
      const settings = location?.plugins?.weather || {};
      row.querySelector('[data-wind-warning]').value = Object.hasOwn(settings, 'warningWindKnots') ? settings.warningWindKnots ?? '' : context.port.plugins?.weather?.warningWindKnots ?? '';
    },
    readConfig(row, previous) {
      const value = row.querySelector('[data-wind-warning]').value;
      return {...previous, warningWindKnots: value === '' ? null : Number(value)};
    },
    readGlobal(settings) { const result = {...settings}; delete result.warningWindKnots; return result; }
  });
}

export function render(context) {
    const {host, track, view, location, api} = context;
    const index = 0;
    const {instant, START, END, DAY, HOUR, dayWidth, finite, severity, shortDate, statusElement, externalUrl} = api;
    api.locationLabel(host, track, location, view, `${track.label} (kn)${finite(track.warningWindKnots) ? ` / Warnung ab ${track.warningWindKnots} kn` : ''}`);
    if (!['ready', 'stale'].includes(track.status)) { host.append(statusElement(track.label, track.message || 'Keine Daten', view, 0)); return; }

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
      const url = externalUrl(track.url);
      const element = document.createElement(url ? 'a' : 'span');
      element.className = 'port-plugin-value';
      if (url) { element.href = url; element.target = '_blank'; element.rel = 'noopener noreferrer'; }
      if (severity(sample.state)) element.classList.add(`plugin-${sample.state}`);
      element.style.left = `${left - 16}px`;
      element.style.top = `${index * 38 + 2}px`;
      const stamp = `${shortDate(instant(sample.time))} UTC`;
      element.title = `${track.label} / ${stamp}\n${sample.label || `${sample.value} ${sample.unit || track.unit || ''}`}\n${track.source?.attribution || track.source?.name || ''}${track.fetchedAt ? `\nStand: ${track.fetchedAt}` : ''}${track.status === 'stale' ? '\nVeralteter Datenstand' : ''}`;
      element.setAttribute('aria-label', element.title);
      if (!url) element.setAttribute('role', 'img');
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

