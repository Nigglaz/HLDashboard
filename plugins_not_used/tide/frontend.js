export function locations(port) {
  return (port.pluginLocations || []).filter(location => location.plugin === 'tide' || !location.plugin && (location.plugins?.tide?.enabled === true || !!location.plugins?.tide?.url));
}

export function mountSettings(context) {
  return context.api.locationSettings({...context, id: 'tide', locations: locations(context.port),
    fill(row, location) {
      const stations = row.querySelector('[data-stations]');
      stations.id = `bsh-${row.dataset.locationId}`;
      const input = row.querySelector('[data-bsh-station]');
      input.setAttribute('list', stations.id);
      input.value = location?.plugins?.tide?.stationId || '';
      row.querySelector('[data-field="url"]').value = location?.plugins?.tide?.url || location?.url || '';
    },
    readConfig(row, previous) {
      const result = {...previous, stationId: row.querySelector('[data-bsh-station]').value.trim()};
      delete result.url;
      return result;
    }
  });
}

export function render(context) {
    const {host, track, view, location, api} = context;
    const index = 0;
    const {instant, START, END, DAY, HOUR, dayWidth, finite, severity, shortDate, statusElement, externalUrl} = api;
    api.locationLabel(host, track, location, view);
    if (!['ready', 'stale'].includes(track.status)) { host.append(statusElement(track.label, track.message || 'Keine Daten', view, 0)); return; }

    const points = (track.samples || []).filter((point) => ['high', 'low'].includes(point.kind) && Number.isFinite(instant(point.time)))
      .map((point) => ({...point, timeValue: instant(point.time), x: view.labelWidth + (instant(point.time) - START) / DAY * dayWidth, y: point.kind === 'high' ? 8 : 30}))
      .sort((first, second) => first.timeValue - second.timeValue);
    const right = track.status === 'stale' ? Math.max(view.left, view.right - 150) : view.right;
    const width = Math.max(0, right - view.left);
    if (!width) return;
    const namespace = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(namespace, 'svg');
    svg.classList.add('port-plugin-tide');
    svg.style.left = `${view.left}px`; svg.style.top = `${index * 38}px`;
    svg.style.width = `${width}px`; svg.style.height = '38px';
    svg.setAttribute('width', width); svg.setAttribute('height', '38');
    svg.setAttribute('viewBox', `0 0 ${width} 38`);
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', `${track.label}: relative Hoch-/Niedrigwasser-Zeitpunkte`);
    const link = externalUrl(track.url);
    let segments = 0, events = 0;
    for (let position = 1; position < points.length; position++) {
      const before = points[position - 1], after = points[position];
      if (before.segmentId !== after.segmentId || before.kind === after.kind || before.timeValue >= after.timeValue || after.x <= view.left || before.x >= right) continue;
      const firstX = before.x - view.left, lastX = after.x - view.left, middle = (firstX + lastX) / 2;
      const path = document.createElementNS(namespace, 'path');
      path.setAttribute('d', `M ${firstX} ${before.y} C ${middle} ${before.y}, ${middle} ${after.y}, ${lastX} ${after.y}`);
      path.classList.add('tide-curve');
      svg.append(path); segments++;
    }
    for (const point of points) {
      if (point.x < view.left + 3 || point.x > right - 3) continue;
      const marker = document.createElementNS(namespace, 'circle');
      marker.setAttribute('cx', point.x - view.left); marker.setAttribute('cy', point.y); marker.setAttribute('r', '2.5');
      marker.classList.add('tide-point'); marker.dataset.time = point.time; marker.dataset.kind = point.kind;
      const titleText = `${track.label} / ${point.kind === 'high' ? 'Hochwasser' : 'Niedrigwasser'} ${shortDate(point.timeValue)} UTC${track.stationId ? `\nBSH-Pegel: ${track.stationId}` : ''}\n${track.accuracyNote || 'Relative Darstellung ohne Hoehenmassstab'}\n${track.source?.attribution || track.source?.name || ''}${track.fetchedAt ? `\nStand: ${track.fetchedAt}` : ''}${track.status === 'stale' ? '\nVeralteter Datenstand' : ''}`;
      const title = document.createElementNS(namespace, 'title'); title.textContent = titleText; marker.append(title);
      marker.setAttribute('aria-label', titleText);
      if (link) {
        const anchor = document.createElementNS(namespace, 'a');
        anchor.setAttribute('href', link); anchor.setAttribute('target', '_blank'); anchor.setAttribute('rel', 'noopener noreferrer');
        anchor.setAttribute('aria-label', titleText); anchor.append(marker); svg.append(anchor);
      } else svg.append(marker);
      events++;
    }
    if (link) {
      const linked = document.createElementNS(namespace, 'a');
      linked.setAttribute('href', link); linked.setAttribute('target', '_blank'); linked.setAttribute('rel', 'noopener noreferrer');
      linked.setAttribute('aria-label', `${track.label}: Standortseite oeffnen`);
      const area = document.createElementNS(namespace, 'rect');
      area.setAttribute('width', width); area.setAttribute('height', '38'); area.classList.add('tide-link-area');
      const title = document.createElementNS(namespace, 'title');
      title.textContent = `${track.label}: Standortseite oeffnen\n${track.accuracyNote || ''}`;
      area.append(title); linked.append(area);
      for (const curve of [...svg.querySelectorAll('path')]) linked.append(curve);
      svg.prepend(linked);
    }
    host.append(svg);
    if (track.status === 'stale') {
      const status = statusElement(track.label, 'veralteter Stand', view, index, 'plugin-stale');
      status.style.left = `${Math.max(view.left, view.right - 150)}px`; host.append(status);
    } else if (!events && !segments) host.append(statusElement(track.label, track.message || 'Keine Tide-Ereignisse im sichtbaren Zeitraum', view, index));
  }

