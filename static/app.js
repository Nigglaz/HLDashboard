const $ = (selector) => document.querySelector(selector);
const DAY = 86400000;
const HOUR = 3600000;
const EPOCH = Date.UTC(2027, 0, 14);
let START = EPOCH;
const addMonths = (value, count) => {
  const date = new Date(value), last = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + count + 1, 0)).getUTCDate();
  return Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + count, Math.min(date.getUTCDate(), last));
};
let END = addMonths(START, 6);
const calendarDays = () => Math.ceil((END - START) / DAY);
function shiftCalendar(start) { const duration = END - START; START = start; END = START + duration; }
const clone = (value) => structuredClone(value);
const instant = (value) => Date.parse(value + 'Z');
const iso = (value) => new Date(value).toISOString().slice(0, 16);
const dateLabel = (value, options = {}) => new Intl.DateTimeFormat('de-DE', {timeZone: 'UTC', ...options}).format(new Date(value));
const shortDate = (value) => dateLabel(value, {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'});
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
let saved, working, selected = 'busan', dayWidth = 64, history = [], future = [], editing = null, problems = [];
let toastTimer, saving = false;
let activeDate = '2027-01-16', selectedService = 'NE2', mode = 'planning', activeProforma = 'initial';
let collapsed = new Set(), hiddenBerths = new Set(), views = {}, activeDrag = false;
let compareProforma = false;
let refreshingData = false, dataChangeNotice = '', dataLoadNotice = '';
const icons = () => { if (globalThis.lucide) lucide.createIcons(); };
const serviceFor = (ship) => saved.services.find((service) => service.id === ship.serviceId);
const dayInstant = (value) => Date.parse(value.slice(0, 10) + 'T00:00Z');
function resolveVoyage(ship, date) {
  const day = date.slice(0, 10);
  if (ship.voyages[day]) return {key: day, source: 'actual', ...ship.voyages[day]};
  const versions = ship.proformas.filter((item) => item.validFrom <= day).sort((left, right) => left.validFrom.localeCompare(right.validFrom));
  if (!versions.length) return null;
  const version = versions.at(-1), period = version.repeatWeeks * 7 * DAY, anchor = instant(version.stops[0].arrival);
  let cycle = Math.floor((dayInstant(day) - dayInstant(version.stops[0].arrival)) / period);
  if (iso(anchor + cycle * period).slice(0, 10) < version.validFrom) cycle++;
  const key = iso(anchor + cycle * period).slice(0, 10);
  if (ship.proformas.some((item) => item.validFrom > version.validFrom && item.validFrom <= key)) return null;
  if (ship.voyages[key]) return {key, source: 'actual', ...ship.voyages[key]};
  const stops = clone(version.stops);
  for (const stop of stops) for (const field of ['arrival', 'departure']) stop[field] = iso(instant(stop[field]) + cycle * period);
  return {key, source: 'proforma', proformaId: version.id, stops};
}
function stopsFor(ship, date = activeDate, editable = false) {
  if (mode === 'proformas') return (ship.proformas.find((item) => item.id === activeProforma) || ship.proformas[0])?.stops || [];
  const voyage = displayVoyage(ship, date);
  if (!voyage) return [];
  if (editable && !ship.voyages[voyage.key]) ship.voyages[voyage.key] = {proformaId: voyage.proformaId, stops: voyage.stops};
  return editable ? ship.voyages[voyage.key].stops : voyage.stops;
}
function displayVoyage(ship, date) {
  let voyage = resolveVoyage(ship, date);
  for (let attempt = 0; voyage && instant(voyage.stops.at(-1).departure) < START && attempt < 200; attempt++) {
    const version = ship.proformas.find((item) => item.id === voyage.proformaId);
    voyage = resolveVoyage(ship, iso(dayInstant(voyage.key) + version.repeatWeeks * 7 * DAY).slice(0, 10));
  }
  return voyage;
}
const shipById = (id, date = activeDate) => { const ship = working.find((item) => item.id === id); return {...ship, stops: stopsFor(ship, date)}; };
const baselineShip = (id, date = activeDate) => { const ship = saved.ships.find((item) => item.id === id); return {...ship, stops: mode === 'proformas' ? (ship.proformas.find((item) => item.id === activeProforma)?.stops || []) : stopsFor(ship, date)}; };
const changed = (shipId, stop, date = activeDate) => JSON.stringify(stop) !== JSON.stringify(baselineShip(shipId, date).stops.find((old) => old.id === stop.id));
const shipDirtyCount = (ship) => Number(JSON.stringify(ship) !== JSON.stringify(saved.ships.find((item) => item.id === ship.id)));
const dirtyCount = () => working.reduce((count, ship) => count + shipDirtyCount(ship), 0);
const routePorts = () => shipById(selected).stops.map((stop) => saved.ports.find((port) => port.id === stop.portId));
function shipColor(ship) {
  const index = working.filter((item) => item.serviceId === ship.serviceId).findIndex((item) => item.id === ship.id);
  return ship.serviceId === 'NE4' ? `hsl(${169 + index * 4} 53% ${35 + index % 3 * 7}%)` : `hsl(${209 + index * 4} 62% ${43 + index % 3 * 6}%)`;
}

function minimumTransit(ship, origin, destination) {
  const from = saved.ports.find((port) => port.id === origin), to = saved.ports.find((port) => port.id === destination);
  const distance = from?.distancesNm?.[destination] ?? to?.distancesNm?.[origin] ?? 100;
  const speed = ship.maxSpeedKnots ?? 20;
  return {distance, speed, hours: distance / speed};
}

function proformaFor(ship, voyage) {
  return resolveVoyage({...ship, voyages: {}}, voyage.key);
}

function referenceHtml(ship, actual, voyage, summary = false) {
  if (!compareProforma || mode !== 'planning' || ship.serviceId !== selectedService) return '';
  const plan = proformaFor(ship, voyage)?.stops.find((stop) => stop.id === actual.id || stop.portId === actual.portId);
  if (!plan) return '';
  const left = (instant(plan.arrival) - START) / DAY * dayWidth;
  const width = (instant(plan.departure) - instant(plan.arrival)) / DAY * dayWidth;
  const color = ship.id === selected ? 'var(--red)' : shipColor(ship);
  const title = `${ship.name} / Proforma\n${shortDate(instant(plan.arrival))} - ${shortDate(instant(plan.departure))}\nLiegeplatz ${plan.berth}`;
  const separate = Math.abs(instant(actual.arrival) - instant(plan.arrival)) / DAY * dayWidth > 60 || actual.berth !== plan.berth;
  return `<div class="proforma-reference ${summary ? 'proforma-stay' : ''}" data-reference-ship="${ship.id}" data-reference-stop="${actual.id}" data-reference-voyage="${voyage.key}" data-plan-arrival="${plan.arrival}" data-reference-type="${summary ? 'stay' : 'berth'}" style="--reference-color:${color};left:${left - 2}px;width:${Math.max(width, 6) + 4}px" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">${separate ? `<span>${escapeHtml(ship.name)}</span>` : ''}</div>`;
}

function renderConnections() {
  const chart = $('#chart');
  chart.querySelector('.proforma-connections')?.remove();
  if (!compareProforma || mode !== 'planning') return;
  const bounds = chart.getBoundingClientRect();
  let links = '';
  for (const reference of chart.querySelectorAll('.proforma-reference')) {
    const {referenceShip: shipId, referenceStop: stopId, referenceVoyage: voyageKey, referenceType: type, planArrival} = reference.dataset;
    const actual = type === 'stay'
      ? chart.querySelector(`.stay-box[data-overview-stop="${stopId}"][data-voyage="${voyageKey}"]`)
      : chart.querySelector(`.bar:not(.ghost)[data-ship="${shipId}"][data-stop="${stopId}"][data-voyage="${voyageKey}"]`);
    if (!actual) continue;
    const ship = working.find((item) => item.id === shipId);
    const stop = resolveVoyage(ship, voyageKey)?.stops.find((item) => item.id === stopId);
    if (!stop) continue;
    const delay = (instant(stop.arrival) - instant(planArrival)) / HOUR;
    const planned = reference.getBoundingClientRect(), current = actual.getBoundingClientRect();
    const fromX = planned.left - bounds.left + Math.min(20, planned.width / 2);
    const toX = current.left - bounds.left + Math.min(20, current.width / 2);
    const fromY = planned.top - bounds.top - 1, toY = current.top - bounds.top - 1;
    const laneY = Math.min(fromY, toY) - 7;
    const hours = Number(delay.toFixed(2));
    const label = `${hours > 0 ? '+' : ''}${hours}h`;
    const color = shipId === selected ? 'var(--red)' : shipColor(ship);
    const labelX = Math.max(parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--label')) + 5, (fromX + toX) / 2);
    const labelWidth = label.length * 5.5 + 10;
    links += `<g style="color:${color}" data-delay-hours="${delay}" data-link-ship="${shipId}" data-link-voyage="${voyageKey}" data-link-type="${type}"><polyline points="${fromX},${fromY} ${fromX},${laneY} ${toX},${laneY} ${toX},${toY}"/><rect x="${labelX}" y="${laneY - 18}" width="${labelWidth}" height="16" rx="2"/><text x="${labelX + 5}" y="${laneY - 6}">${escapeHtml(label)}</text></g>`;
  }
  chart.insertAdjacentHTML('beforeend', `<svg class="proforma-connections" width="${chart.scrollWidth}" height="${chart.scrollHeight}" style="width:${chart.scrollWidth}px;height:${chart.scrollHeight}px" aria-label="Proforma-Abweichungen">${links}</svg>`);
}

function notify(message, error = false) {
  clearTimeout(toastTimer);
  $('#toast').textContent = message;
  $('#toast').classList.toggle('error', error);
  $('#toast').hidden = false;
  toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 5000);
}

function persistDraft() {
  try {
    if (dirtyCount()) localStorage.setItem('harborline-draft', JSON.stringify({revision: saved.revision, dataSignature: saved.dataSignature, baseShips: saved.ships, ships: working, mode, activeProforma, selected, activeDate}));
    else localStorage.removeItem('harborline-draft');
  } catch { notify('Der Browser kann den Entwurf nicht zwischenspeichern.', true); }
}

function commit(next) {
  if (mode !== 'planning') return;
  if (mode === 'planning') for (const ship of next) for (const key of Object.keys(ship.voyages)) {
    const original = saved.ships.find((item) => item.id === ship.id);
    if (original.voyages[key]) continue;
    const candidate = ship.voyages[key], fallbackShip = clone(ship);
    delete fallbackShip.voyages[key];
    const fallback = resolveVoyage(fallbackShip, key);
    if (fallback && JSON.stringify(candidate.stops) === JSON.stringify(fallback.stops)) delete ship.voyages[key];
  }
  if (JSON.stringify(next) === JSON.stringify(working)) return;
  history.push(clone(working));
  if (history.length > 100) history.shift();
  future = [];
  working = next;
  persistDraft();
  render();
}

function findProblemsFor(source) {
  const found = [], occupied = new Map();
  for (const raw of source) {
    for (const voyage of visibleVoyages(raw)) {
    const ship = {...raw, stops: voyage.stops};
    ship.stops.forEach((stop, index) => {
      const port = saved.ports.find((item) => item.id === stop.portId);
      const start = instant(stop.arrival), end = instant(stop.departure);
      const identity = `${ship.id}:${voyage.key}:${stop.id}`;
      if (!(end > start)) found.push({key: `duration:${identity}`, severity: Infinity, occurrences: [identity], ids: [stop.id], message: `${ship.name}: Abfahrt vor Ankunft.`});
      if (index) {
        const previous = ship.stops[index - 1];
        const minimum = minimumTransit(ship, previous.portId, stop.portId);
        const available = (start - instant(previous.departure)) / HOUR;
        if (available < minimum.hours - 1e-9) found.push({key: `transit:${identity}`, severity: (minimum.hours - available) * HOUR, occurrences: [identity, `${ship.id}:${voyage.key}:${previous.id}`], ids: [stop.id, previous.id], message: `${ship.name}: Transit nach ${port.name} zu kurz: ${Number(available.toFixed(2))} h verf\u00fcgbar, mindestens ${Number(minimum.hours.toFixed(2))} h (${minimum.distance} sm / ${minimum.speed} kn).`});
      }
      const key = `${stop.portId}-${stop.berth}`;
      for (const other of occupied.get(key) || []) {
        if (start < other.end && end > other.start) found.push({key: `berth:${[identity, other.identity].sort().join(':')}`, severity: Math.min(end, other.end) - Math.max(start, other.start), occurrences: [identity, other.identity], ids: [stop.id, other.id], message: `${port.name}, Platz ${stop.berth}: ${ship.name} / ${other.name}.`});
      }
      if (!occupied.has(key)) occupied.set(key, []);
      occupied.get(key).push({id: stop.id, identity, name: ship.name, start, end});
    });
    }
  }
  return found;
}

function findProblems() {
  const old = new Map(findProblemsFor(saved.ships).map((issue) => [issue.key, issue.severity]));
  return findProblemsFor(working).map((issue) => ({...issue, isNew: issue.severity > (old.get(issue.key) || 0)}));
}

function barHtml(ship, stop, ghost = false, voyageDate = activeDate) {
  const left = (instant(stop.arrival) - START) / DAY * dayWidth;
  const width = (instant(stop.departure) - instant(stop.arrival)) / DAY * dayWidth;
  const dirty = mode === 'planning' && !ghost && changed(ship.id, stop, voyageDate);
  const classes = ['bar', ghost ? 'ghost' : ship.id === selected ? 'selected' : '', dirty ? 'draft' : ''].join(' ');
  const title = `${ship.name}${ghost ? ' / Bisher gespeichert' : ''}\n${shortDate(instant(stop.arrival))} - ${shortDate(instant(stop.departure))}\nLiegeplatz ${stop.berth}${dirty ? '\nUngespeicherter Entwurf' : ''}`;
  return `<div class="${classes}" style="--ship-color:${shipColor(ship)};left:${left}px;width:${Math.max(width, 6)}px" ${ghost ? '' : `data-ship="${ship.id}" data-stop="${stop.id}" data-voyage="${voyageDate}" tabindex="0" role="button" aria-label="${escapeHtml(title)}"`} title="${escapeHtml(title)}">${escapeHtml(ship.name)}${ghost || mode === 'proformas' ? '' : '<span class="resize-handle" title="Abfahrt verschieben"></span>'}</div>`;
}

function visibleVoyages(ship) {
  if (mode === 'proformas') return [{key: activeDate, stops: stopsFor(ship)}];
  const result = new Map();
  for (const version of ship.proformas) {
    const period = version.repeatWeeks * 7 * DAY, anchor = instant(version.stops[0].arrival);
    let cycle = Math.floor((START - anchor) / period) - 1;
    while (anchor + cycle * period < END) {
      const key = iso(anchor + cycle * period).slice(0, 10);
      if (key >= version.validFrom) {
        const voyage = resolveVoyage(ship, key);
        if (voyage?.key === key) result.set(key, voyage);
      }
      cycle++;
    }
  }
  for (const [key, voyage] of Object.entries(ship.voyages)) result.set(key, {key, ...voyage});
  return [...result.values()].filter((voyage) => instant(voyage.stops[0].arrival) < END && instant(voyage.stops.at(-1).departure) >= START);
}

function transitRow(position, port, nextPort, voyages) {
  const ship = working.find((item) => item.id === selected);
  let content = '';
  for (const voyage of voyages) {
    const stay = voyage.stops.find((stop) => stop.portId === port.id);
    const next = nextPort ? voyage.stops.find((stop) => stop.portId === nextPort.id) : null;
    if (!stay) continue;
    const duration = (instant(stay.departure) - instant(stay.arrival)) / HOUR;
    const left = (instant(stay.arrival) - START) / DAY * dayWidth;
    const width = duration / 24 * dayWidth;
    content += `<button type="button" class="stay-box" data-overview-stop="${stay.id}" data-voyage="${voyage.key}" style="left:${left}px;width:${Math.max(width, 6)}px" title="${escapeHtml(ship.name)}\nLiegezeit: ${duration} h"><strong>${escapeHtml(ship.name)}</strong><span>Liegezeit: ${duration} h</span></button>`;
    content += referenceHtml(ship, stay, voyage, true);
    if (next) {
      const gap = (instant(next.arrival) - instant(stay.departure)) / HOUR;
      const minimum = minimumTransit(ship, stay.portId, next.portId);
      const transitLeft = (instant(stay.departure) - START) / DAY * dayWidth;
      content += `<form class="transit-editor" data-transit="${next.id}" data-voyage="${voyage.key}" style="left:${transitLeft}px"><span>${escapeHtml(port.name)} &rarr; ${escapeHtml(nextPort.name)}</span><label><input type="number" min="0" max="10000" step="0.25" value="${next.transitMinutes / 60}" aria-label="Transit nach ${escapeHtml(nextPort.name)} in Stunden" required ${mode === 'proformas' ? 'disabled' : ''}> h</label><button type="submit" title="Transit anwenden und Ankunft neu berechnen" aria-label="Transit anwenden" ${mode === 'proformas' ? 'hidden' : ''}>&#10003;</button><small class="${gap < minimum.hours ? 'negative-gap' : ''}">${Math.round(gap * 100) / 100} h verf\u00fcgbar / min. ${Number(minimum.hours.toFixed(2))} h (${minimum.distance} sm / ${minimum.speed} kn)</small></form>`;
    }
  }
  return `<div class="transit-row"><div class="transit-label">${nextPort ? `Transit ${position + 1}` : 'Ankunft / Liegezeit'}</div><div class="transit-track" style="width:${calendarDays() * dayWidth}px">${content}</div></div>`;
}

function renderChart() {
  const DAYS = calendarDays();
  const chart = $('#chart');
  chart.style.width = `calc(var(--label) + ${DAYS * dayWidth}px)`;
  chart.style.setProperty('--day', `${dayWidth}px`);
  chart.classList.toggle('compare-proforma', compareProforma && mode === 'planning');
  let days = '';
  let weekendBands = '';
  for (let index = 0; index < DAYS; index++) {
    const date = new Date(START + index * DAY);
    const weekend = [0, 6].includes(date.getUTCDay());
    const hours = dayWidth >= 240 ? `<div class="hour-labels">${Array.from({length: 8}, (_, hour) => `<span>${String(hour * 3).padStart(2, '0')}:00</span>`).join('')}</div>` : '';
    days += `<div class="day ${weekend ? 'weekend' : ''} ${date.getUTCDay() === 1 ? 'week-start' : ''}">${dateLabel(date, {day: '2-digit', month: '2-digit'})}<small>${dateLabel(date, {weekday: 'short'})}</small>${hours}</div>`;
    if (weekend) weekendBands += `<span class="weekend-band" style="left:${index * dayWidth}px;width:${dayWidth}px"></span>`;
  }
  let html = `<div class="time-header"><div class="time-corner">HAFEN / LIEGEPLATZ</div><div class="time-days">${days}</div></div>`;
  const route = shipById(selected).stops;
  const selectedVoyages = visibleVoyages(working.find((ship) => ship.id === selected));
  const ports = routePorts();
  for (const [position, port] of routePorts().entries()) {
    if (position) {
      html += transitRow(position - 1, ports[position - 1], port, selectedVoyages);
    }
    html += `<div class="port-heading"><button class="port-label port-toggle" data-collapse="${port.id}" aria-expanded="${!collapsed.has(port.id)}" title="Hafen ein- oder ausklappen"><span class="chevron ${collapsed.has(port.id) ? 'closed' : ''}">&#9662;</span>${escapeHtml(port.name)}</button><div class="port-note">${port.berths} LIEGEPL${port.berths === 1 ? 'ATZ' : '&Auml;TZE'}</div></div>`;
    if (collapsed.has(port.id)) continue;
    for (let berth = 1; berth <= port.berths; berth++) {
      if (hiddenBerths.has(`${port.id}:${berth}`)) continue;
      let bars = '';
      for (const raw of working) {
        for (const voyage of visibleVoyages(raw)) {
        const ship = {...raw, stops: voyage.stops};
        for (const stop of ship.stops.filter((item) => item.portId === port.id)) {
          const old = baselineShip(ship.id, voyage.key).stops.find((item) => item.id === stop.id);
          if (changed(ship.id, stop, voyage.key) && old?.berth === berth) bars += barHtml(ship, old, true, voyage.key);
          if (stop.berth === berth) bars += barHtml(ship, stop, false, voyage.key);
          const planned = proformaFor(raw, voyage)?.stops.find((item) => item.id === stop.id || item.portId === stop.portId);
          if (planned?.berth === berth && planned.portId === port.id) bars += referenceHtml(ship, stop, voyage);
        }
        }
      }
      html += `<div class="berth-row" data-port="${port.id}" data-berth="${berth}"><div class="berth-label">Liegeplatz ${berth}</div><div class="track" style="width:${DAYS * dayWidth}px">${weekendBands}${bars}</div></div>`;
    }
  }
  if (ports.length) html += transitRow(ports.length - 1, ports.at(-1), null, selectedVoyages);
  chart.innerHTML = html;
  chart.classList.toggle('hourly', dayWidth >= 240);
  chart.classList.toggle('proforma-readonly', mode === 'proformas');
  $('#visible-range').textContent = `${dateLabel(START, {day: '2-digit', month: '2-digit', year: 'numeric'})} - ${dateLabel(START + (DAYS - 1) * DAY, {day: '2-digit', month: '2-digit', year: 'numeric'})}`;
  $('#timeline-start').value = iso(START).slice(0, 10);
  $('#timeline-end').value = iso(END - DAY).slice(0, 10);
  renderConnections();
}

function renderSidebar() {
  $('#fleet').innerHTML = working.filter((ship) => ship.serviceId === selectedService).map((ship) => {
    const count = shipDirtyCount(ship);
    return `<button class="fleet-button ${ship.id === selected ? 'active' : ''}" data-select="${ship.id}" style="--ship-color:${shipColor(ship)}"><span class="vessel-dot"></span><span>${escapeHtml(ship.name)}<small class="fleet-service">${ship.serviceId}</small></span>${count ? '<span class="vessel-draft">Pending</span>' : ''}</button>`;
  }).join('');
  const ship = shipById(selected);
  $('#route').innerHTML = ship.stops.map((stop, index) => `<div class="route-stop"><button data-detail="${stop.id}">${escapeHtml(saved.ports.find((port) => port.id === stop.portId).name)}</button><div class="route-time">${shortDate(instant(stop.arrival))}</div>${index ? `<button class="transit" data-detail="${stop.id}" title="Transit bearbeiten">${stop.transitMinutes / 60} h Transit</button>` : ''}</div>`).join('');
  const visibleProblems = [...new Map(problems.map((item) => [`${item.isNew}:${item.message}`, item])).values()];
  $('#route-count').textContent = `${ship.stops.length} H\u00e4fen`;
  $('#fleet-count').textContent = String(working.filter((ship) => ship.serviceId === selectedService).length).padStart(2, '0');
  $('#conflict-count').textContent = visibleProblems.length ? `${visibleProblems.length} HINWEIS${visibleProblems.length > 1 ? 'E' : ''}` : 'OK';
  $('#conflict-count').classList.toggle('error', visibleProblems.some((item) => item.isNew));
  $('#conflicts').innerHTML = visibleProblems.length ? visibleProblems.map((item) => `<div class="conflict-item">${item.isNew ? 'Neu' : 'Bestand'}<br>${escapeHtml(item.message)}</div>`).join('') : '<p class="conflict-good">Keine Doppelbelegungen.<br>Transitzeiten eingehalten.</p>';
}

function render() {
  const selectedShip = working.find((ship) => ship.id === selected);
  selectedService = selectedShip.serviceId;
  if (!selectedShip.proformas.some((version) => version.id === activeProforma)) activeProforma = selectedShip.proformas[0].id;
  problems = findProblems();
  renderChart();
  renderSidebar();
  const count = dirtyCount();
  $('#service-select').value = selectedService;
  $('#draft-count').textContent = shipDirtyCount(selectedShip);
  $('#undo').disabled = !history.length || saving || mode !== 'planning';
  $('#redo').disabled = !future.length || saving || mode !== 'planning';
  $('#discard').disabled = !shipDirtyCount(selectedShip) || saving || mode !== 'planning';
  const selectedOnly = saved.ships.map((ship) => ship.id === selected ? selectedShip : ship);
  const oldIssues = new Map(findProblemsFor(saved.ships).map((item) => [item.key, item.severity]));
  const newIssues = findProblemsFor(selectedOnly).filter((item) => item.severity > (oldIssues.get(item.key) || 0));
  $('#save').disabled = !shipDirtyCount(selectedShip) || !!newIssues.length || saving;
  $('#save').hidden = mode !== 'planning';
  $('#undo').hidden = $('#redo').hidden = $('#discard').hidden = mode !== 'planning';
  $('#cascade').closest('label').hidden = mode !== 'planning';
  $('#compare-proforma').closest('label').hidden = mode !== 'planning';
  $('#compare-proforma').checked = compareProforma;
  $('#status').textContent = mode === 'proformas' ? 'Proforma \u00b7 schreibgesch\u00fctzt' : newIssues.length ? `${newIssues.length} Konflikte bei Einzel\u00fcbernahme` : count ? `${count} Schiffe mit offenen \u00c4nderungen` : 'Aktueller Plan';
  $('#voyage').value = activeDate;
  const rawSelected = working.find((ship) => ship.id === selected);
  const resolved = displayVoyage(rawSelected, activeDate);
  $('#service-info').textContent = mode === 'proformas' ? 'PROFORMA' : resolved ? `${resolved.source === 'actual' ? 'Fahrplan' : 'Proforma'} / ${resolved.key}` : 'Keine g\u00fcltige Proforma';
  $('#reset-voyage').hidden = mode !== 'planning' || resolved?.source !== 'actual';
  $('#reset-voyage').disabled = saving;
  $('#save-label').textContent = 'Plan f\u00fcr dieses Schiff \u00fcbernehmen';
  $('#tab-planning').classList.toggle('nav-active', mode === 'planning');
  $('#tab-proformas').classList.toggle('nav-active', mode === 'proformas');
  $('#proforma-toolbar').hidden = mode !== 'proformas';
  $('#voyage-control').hidden = mode === 'proformas';
  renderProformaControls();
  $('#zoom').value = dayWidth;
  $('#stop-count').textContent = working.reduce((count, raw) => count + visibleVoyages(raw).reduce((total, voyage) => total + voyage.stops.filter((stop) => routePorts().some((port) => port.id === stop.portId)).length, 0), 0);
  renderBerthOptions();
}

function selectShip(id, focus = false) {
  selected = id;
  selectedService = working.find((ship) => ship.id === id).serviceId;
  if (!working.find((ship) => ship.id === id).proformas.some((item) => item.id === activeProforma)) activeProforma = working.find((ship) => ship.id === id).proformas[0].id;
  $('#inspector').hidden = true;
  render();
  if (focus) focusShip();
}

function focusShip() {
  const first = shipById(selected).stops[0];
  if (!first) return;
  if (instant(first.arrival) < START || instant(first.arrival) >= END) {
    shiftCalendar(dayInstant(first.arrival) - 2 * DAY);
    renderChart();
  }
  $('#chart-scroll').scrollTo({left: Math.max(0, (instant(first.arrival) - START) / DAY * dayWidth - 36), top: 0, behavior: 'smooth'});
}

function openInspector(shipId, stopId, date = activeDate) {
  editing = {shipId, stopId, date};
  const ship = shipById(shipId, date), stop = ship.stops.find((item) => item.id === stopId);
  const port = saved.ports.find((item) => item.id === stop.portId);
  $('#detail-ship').textContent = `${ship.name} / ${ship.serviceId} / ${mode === 'proformas' ? 'Proforma' : date}`;
  $('#detail-port').textContent = port.name;
  $('#detail-berth').innerHTML = Array.from({length: port.berths}, (_, index) => `<option value="${index + 1}">Liegeplatz ${index + 1}</option>`).join('');
  $('#detail-berth').value = stop.berth;
  $('#detail-arrival').value = stop.arrival;
  $('#detail-departure').value = stop.departure;
  $('#detail-transit').value = stop.transitMinutes / 60;
  const first = ship.stops[0].id === stopId;
  $('#detail-transit').disabled = first;
  $('#recalculate').disabled = first;
  $('#recalculate').checked = false;
  $('#detail-error').textContent = '';
  const readOnly = mode === 'proformas';
  for (const field of ['#detail-berth', '#detail-arrival', '#detail-departure']) $(field).disabled = readOnly;
  $('#detail-transit').disabled = readOnly || first;
  $('#recalculate').disabled = readOnly || first;
  $('#stop-form button[type="submit"]').hidden = readOnly;
  $('#inspector').hidden = false;
}

function shiftStops(ship, from, delta) {
  for (let index = from; index < ship.stops.length; index++) {
    ship.stops[index].arrival = iso(instant(ship.stops[index].arrival) + delta);
    ship.stops[index].departure = iso(instant(ship.stops[index].departure) + delta);
  }
}

function renderBerthOptions() {
  $('#berth-options').innerHTML = routePorts().map((port) => `<fieldset><legend>${escapeHtml(port.name)}</legend><label class="checkbox-label"><input type="checkbox" data-view-collapse="${port.id}" ${collapsed.has(port.id) ? 'checked' : ''}> Hafen eingeklappt</label><div class="berth-checks">${Array.from({length: port.berths}, (_, index) => `<label><input type="checkbox" data-visible-berth="${port.id}:${index + 1}" ${hiddenBerths.has(`${port.id}:${index + 1}`) ? '' : 'checked'}> LP ${index + 1}</label>`).join('')}</div></fieldset>`).join('');
}

function renderProformaControls() {
  const ship = working.find((item) => item.id === selected);
  const version = ship.proformas.find((item) => item.id === activeProforma) || ship.proformas[0];
  activeProforma = version.id;
  $('#proforma-select').innerHTML = [...ship.proformas].sort((left, right) => left.validFrom.localeCompare(right.validFrom)).map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} / ab ${item.validFrom}</option>`).join('');
  $('#proforma-select').value = version.id;
  $('#proforma-name').value = version.name;
  $('#proforma-start').value = version.validFrom;
  $('#proforma-weeks').value = version.repeatWeeks;
}

function switchMode(nextMode) {
  if (saving) return;
  if (mode === nextMode) return;
  mode = nextMode;
  $('#inspector').hidden = true;
  render();
  focusShip();
}
$('#tab-planning').addEventListener('click', () => switchMode('planning'));
$('#tab-proformas').addEventListener('click', () => switchMode('proformas'));
$('#proforma-select').addEventListener('change', (event) => {
  activeProforma = event.target.value;
  render();
  focusShip();
});

$('#collapse-all').addEventListener('click', () => { collapsed = new Set(routePorts().map((port) => port.id)); renderChart(); renderBerthOptions(); });
$('#expand-all').addEventListener('click', () => { collapsed.clear(); renderChart(); renderBerthOptions(); });
$('#reset-voyage').addEventListener('click', () => {
  if (saving || mode !== 'planning') return;
  const next = clone(working), ship = next.find((item) => item.id === selected), voyage = displayVoyage(ship, activeDate);
  if (!voyage || !ship.voyages[voyage.key] || !confirm('Den tats\u00e4chlichen Fahrplan dieser Reise entfernen und wieder die g\u00fcltige Proforma verwenden?')) return;
  delete ship.voyages[voyage.key];
  commit(next);
});

function zoomAt(value, clientX = null) {
  if (activeDrag || !saved) return;
  const scroll = $('#chart-scroll'), rect = scroll.getBoundingClientRect();
  const labelWidth = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--label'));
  const anchor = clientX === null ? (scroll.clientWidth - labelWidth) / 2 : Math.max(0, clientX - rect.left - labelWidth);
  const time = (scroll.scrollLeft + anchor) / dayWidth;
  dayWidth = Math.max(16, Math.min(1200, Math.round(value)));
  const top = scroll.scrollTop;
  renderChart();
  scroll.scrollLeft = time * dayWidth - anchor;
  scroll.scrollTop = top;
  $('#zoom').value = dayWidth;
}

function populateViews(name = '') {
  $('#view-select').innerHTML = '<option value="">Individuell</option>' + Object.keys(views).map((key) => `<option value="${escapeHtml(key)}">${escapeHtml(key)}</option>`).join('');
  $('#view-select').value = name;
}

function applyView(config) {
  collapsed = new Set(config.collapsed);
  hiddenBerths = new Set(config.hiddenBerths);
  dayWidth = config.dayWidth;
  compareProforma = config.compareProforma === true;
  activeDate = config.voyageDate || config.start.slice(0, 10);
  START = instant(config.start);
  END = config.end ? dayInstant(config.end) + DAY : addMonths(START, 6);
  selected = config.selected;
  selectedService = working.find((ship) => ship.id === selected).serviceId;
  $('#inspector').hidden = true;
  render();
  $('#chart-scroll').scrollLeft = config.scrollLeft;
  $('#chart-scroll').scrollTop = config.scrollTop;
}

$('#berth-options').addEventListener('change', (event) => {
  const input = event.target;
  if (input.dataset.visibleBerth) {
    if (input.checked) hiddenBerths.delete(input.dataset.visibleBerth); else hiddenBerths.add(input.dataset.visibleBerth);
  }
  if (input.dataset.viewCollapse) {
    if (input.checked) collapsed.add(input.dataset.viewCollapse); else collapsed.delete(input.dataset.viewCollapse);
  }
  $('#view-select').value = '';
  renderChart();
});

$('#chart').addEventListener('click', (event) => {
  const stay = event.target.closest('[data-overview-stop]');
  if (stay) { openInspector(selected, stay.dataset.overviewStop, stay.dataset.voyage); return; }
  const toggle = event.target.closest('[data-collapse]');
  if (!toggle || activeDrag) return;
  const id = toggle.dataset.collapse;
  if (collapsed.has(id)) collapsed.delete(id); else collapsed.add(id);
  $('#view-select').value = '';
  renderChart();
  renderBerthOptions();
});

$('#chart').addEventListener('submit', (event) => {
  const form = event.target.closest('[data-transit]');
  if (!form) return;
  event.preventDefault();
  if (saving || mode !== 'planning') return;
  const hours = Number(form.querySelector('input').value);
  if (!Number.isFinite(hours) || hours < 0) return;
  const next = clone(working), raw = next.find((ship) => ship.id === selected);
  const ship = {...raw, stops: stopsFor(raw, form.dataset.voyage, true)};
  const index = ship.stops.findIndex((stop) => stop.id === form.dataset.transit), stop = ship.stops[index];
  const transitMinutes = Math.round(hours * 60);
  const delta = instant(ship.stops[index - 1].departure) + transitMinutes * 60000 - instant(stop.arrival);
  stop.transitMinutes = transitMinutes;
  if ($('#cascade').checked) shiftStops(ship, index, delta);
  else {
    stop.arrival = iso(instant(stop.arrival) + delta);
    stop.departure = iso(instant(stop.departure) + delta);
  }
  commit(next);
});

$('#chart-scroll').addEventListener('wheel', (event) => {
  if (event.target.closest('input,select') || activeDrag) return;
  event.preventDefault();
  const scale = event.deltaMode === 1 ? 18 : event.deltaMode === 2 ? 600 : 1;
  if (event.ctrlKey || event.metaKey) zoomAt(dayWidth * Math.exp(-event.deltaY * scale * 0.002), event.clientX);
  else if (event.shiftKey) $('#chart-scroll').scrollTop += event.deltaY * scale;
  else $('#chart-scroll').scrollLeft += (event.deltaX || event.deltaY) * scale;
}, {passive: false});
$('#chart-scroll').title = 'Mausrad: Zeitachse verschieben | Strg + Mausrad: Zoom | Umschalt + Mausrad: vertikal';

$('#voyage').addEventListener('change', (event) => {
  if (!event.target.value) return;
  activeDate = event.target.value;
  shiftCalendar(dayInstant(activeDate) - 2 * DAY);
  $('#inspector').hidden = true;
  render();
  focusShip();
});
$('#timeline-start').addEventListener('change', (event) => {
  if (!event.target.value) return;
  START = Date.parse(event.target.value + 'T00:00Z');
  if (START >= END) END = addMonths(START, 6);
  activeDate = event.target.value;
  $('#inspector').hidden = true;
  render();
  $('#chart-scroll').scrollLeft = 0;
});
$('#timeline-end').addEventListener('change', (event) => {
  if (!event.target.value) return;
  const end = dayInstant(event.target.value) + DAY;
  if (end <= START) {
    notify('Das Ende muss am oder nach dem Beginn liegen.', true);
    event.target.value = iso(END - DAY).slice(0, 10);
    return;
  }
  END = end;
  $('#view-select').value = '';
  render();
});
$('#view-select').addEventListener('change', (event) => {
  const name = event.target.value;
  if (!views[name]) return;
  applyView(views[name]);
  $('#view-name').value = name;
  try { localStorage.setItem('harborline-view', name); } catch {}
});
$('#save-view').addEventListener('click', async () => {
  const name = $('#view-name').value.trim();
  if (!name) { notify('Bitte einen Namen f\u00fcr die Ansicht eingeben.', true); return; }
  const config = {collapsed: [...collapsed], hiddenBerths: [...hiddenBerths], dayWidth, voyageDate: activeDate,
    start: iso(START), end: iso(END - DAY), selected, compareProforma, scrollLeft: $('#chart-scroll').scrollLeft, scrollTop: $('#chart-scroll').scrollTop};
  try {
    const response = await fetch('/api/views', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, config})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Ansicht konnte nicht gespeichert werden.');
    views = result;
    populateViews(name);
    try { localStorage.setItem('harborline-view', name); } catch {}
    $('#view-options').open = false;
    notify('Ansicht gespeichert.');
  } catch (error) { notify(error.message, true); }
});
$('#reset-view').addEventListener('click', () => {
  collapsed.clear(); hiddenBerths.clear(); $('#view-select').value = '';
  renderChart(); renderBerthOptions();
});

$('#stop-form').addEventListener('submit', (event) => {
  event.preventDefault();
  if (saving || mode !== 'planning') return;
  const next = clone(working), ship = next.find((item) => item.id === editing.shipId);
  const editableShip = {...ship, stops: stopsFor(ship, editing.date, true)};
  const index = editableShip.stops.findIndex((item) => item.id === editing.stopId), stop = editableShip.stops[index];
  const oldDeparture = instant(stop.departure);
  let arrival = instant($('#detail-arrival').value), departure = instant($('#detail-departure').value);
  const transit = Math.round(Number($('#detail-transit').value) * 60);
  if ($('#recalculate').checked && index) {
    const computed = instant(editableShip.stops[index - 1].departure) + transit * 60000;
    departure += computed - arrival;
    arrival = computed;
  }
  if (!Number.isFinite(arrival) || !Number.isFinite(departure) || departure <= arrival || transit < 0) {
    $('#detail-error').textContent = 'Bitte g\u00fcltige Zeiten eingeben. Die Abfahrt muss nach der Ankunft liegen.';
    return;
  }
  Object.assign(stop, {arrival: iso(arrival), departure: iso(departure), berth: Number($('#detail-berth').value), transitMinutes: transit});
  if ($('#cascade').checked) shiftStops(editableShip, index + 1, departure - oldDeparture);
  commit(next);
  $('#inspector').hidden = true;
});

$('#chart').addEventListener('keydown', (event) => {
  const bar = event.target.closest('.bar[data-stop]');
  if (bar && ['Enter', ' '].includes(event.key)) {
    event.preventDefault();
    selected = bar.dataset.ship;
    render();
    openInspector(bar.dataset.ship, bar.dataset.stop, bar.dataset.voyage);
  }
});

$('#chart').addEventListener('pointerdown', (event) => {
  const bar = event.target.closest('.bar[data-stop]');
  if (!bar || event.button !== 0 || saving) return;
  if (mode === 'proformas') {
    openInspector(bar.dataset.ship, bar.dataset.stop, bar.dataset.voyage);
    return;
  }
  activeDrag = true;
  event.preventDefault();
  const shipId = bar.dataset.ship, stopId = bar.dataset.stop;
  const voyageDate = bar.dataset.voyage;
  const ship = shipById(shipId, voyageDate), index = ship.stops.findIndex((stop) => stop.id === stopId), stop = ship.stops[index];
  const resize = event.target.classList.contains('resize-handle');
  const originX = event.clientX, originY = event.clientY;
  const originalScroll = $('#chart-scroll').scrollLeft;
  const originalLeft = parseFloat(bar.style.left), originalWidth = parseFloat(bar.style.width);
  const berthTargets = [...document.querySelectorAll(`.berth-row[data-port="${stop.portId}"] .track`)]
    .map((track) => ({berth: Number(track.parentElement.dataset.berth), top: track.getBoundingClientRect().top, bottom: track.getBoundingClientRect().bottom}));
  const originalScrollTop = $('#chart-scroll').scrollTop;
  let moved = false, delta = 0, targetBerth = stop.berth;
  bar.setPointerCapture(event.pointerId);
  function move(moveEvent) {
    const offset = moveEvent.clientX - originX + $('#chart-scroll').scrollLeft - originalScroll;
    if (Math.abs(offset) < 4 && Math.abs(moveEvent.clientY - originY) < 4 && !moved) return;
    moved = true;
    delta = Math.round(offset / dayWidth * 24) * HOUR;
    if (resize) delta = Math.max(HOUR - (instant(stop.departure) - instant(stop.arrival)), delta);
    bar.classList.add('dragging');
    if (resize) bar.style.width = `${originalWidth + delta / DAY * dayWidth}px`;
    else {
      bar.style.left = `${originalLeft + delta / DAY * dayWidth}px`;
      const pointerY = moveEvent.clientY + $('#chart-scroll').scrollTop - originalScrollTop;
      const currentTarget = berthTargets.find((target) => target.berth === targetBerth);
      if (pointerY < currentTarget.top - 3 || pointerY > currentTarget.bottom + 3) {
        const target = berthTargets.find((candidate) => pointerY >= candidate.top && pointerY < candidate.bottom);
        if (target) targetBerth = target.berth;
      }
      const target = document.querySelector(`.berth-row[data-port="${stop.portId}"][data-berth="${targetBerth}"] .track`);
      const source = bar.parentElement;
      bar.style.transform = `translateY(${target.getBoundingClientRect().top - source.getBoundingClientRect().top}px)`;
    }
    $('#status').textContent = `${ship.name} · ${delta >= 0 ? '+' : ''}${delta / HOUR} h · Liegeplatz ${targetBerth}`;
  }
  function finish(finishEvent) {
    activeDrag = false;
    bar.removeEventListener('pointermove', move);
    bar.removeEventListener('pointerup', finish);
    bar.removeEventListener('pointercancel', cancel);
    if (bar.hasPointerCapture(event.pointerId)) bar.releasePointerCapture(event.pointerId);
    if (!moved) {
      selected = shipId;
      render();
      openInspector(shipId, stopId, voyageDate);
      return;
    }
    const next = clone(working), raw = next.find((item) => item.id === shipId);
    const nextShip = {...raw, stops: stopsFor(raw, voyageDate, true)}, nextStop = nextShip.stops[index];
    selected = shipId;
    if (resize) {
      nextStop.departure = iso(instant(nextStop.departure) + delta);
      if ($('#cascade').checked) shiftStops(nextShip, index + 1, delta);
    } else {
      if ($('#cascade').checked) shiftStops(nextShip, index, delta);
      else {
        nextStop.arrival = iso(instant(nextStop.arrival) + delta);
        nextStop.departure = iso(instant(nextStop.departure) + delta);
      }
      nextStop.berth = targetBerth;
    }
    commit(next);
    render();
  }
  function cancel() {
    activeDrag = false;
    bar.removeEventListener('pointermove', move);
    bar.removeEventListener('pointerup', finish);
    bar.removeEventListener('pointercancel', cancel);
    render();
  }
  bar.addEventListener('pointermove', move);
  bar.addEventListener('pointerup', finish);
  bar.addEventListener('pointercancel', cancel);
});

$('#inspector-handle').addEventListener('pointerdown', (event) => {
  if (event.target.closest('button')) return;
  const panel = $('#inspector'), header = $('#inspector-handle'), rect = panel.getBoundingClientRect();
  const offsetX = event.clientX - rect.left, offsetY = event.clientY - rect.top;
  header.setPointerCapture(event.pointerId);
  function move(moveEvent) {
    panel.style.right = 'auto';
    panel.style.left = `${Math.max(8, Math.min(innerWidth - rect.width - 8, moveEvent.clientX - offsetX))}px`;
    panel.style.top = `${Math.max(8, Math.min(innerHeight - 70, moveEvent.clientY - offsetY))}px`;
  }
  function finish() { header.removeEventListener('pointermove', move); header.removeEventListener('pointerup', finish); header.removeEventListener('pointercancel', finish); }
  header.addEventListener('pointermove', move);
  header.addEventListener('pointerup', finish);
  header.addEventListener('pointercancel', finish);
});

$('#service-select').addEventListener('change', (event) => {
  selectedService = event.target.value;
  selectShip(working.find((ship) => ship.serviceId === selectedService).id, true);
});
$('#fleet').addEventListener('click', (event) => { const button = event.target.closest('[data-select]'); if (button) selectShip(button.dataset.select, true); });
$('#route').addEventListener('click', (event) => { const button = event.target.closest('[data-detail]'); if (button) openInspector(selected, button.dataset.detail); });
$('#focus').addEventListener('click', focusShip);
$('#zoom').addEventListener('input', (event) => zoomAt(Number(event.target.value)));
$('#compare-proforma').addEventListener('change', (event) => {
  compareProforma = event.target.checked;
  $('#view-select').value = '';
  renderChart();
});
let comparisonFrame;
globalThis.addEventListener('resize', () => {
  cancelAnimationFrame(comparisonFrame);
  comparisonFrame = requestAnimationFrame(renderConnections);
});
$('#close-inspector').addEventListener('click', () => { $('#inspector').hidden = true; });
$('#undo').addEventListener('click', () => { if (!history.length) return; future.push(clone(working)); working = history.pop(); $('#inspector').hidden = true; persistDraft(); render(); });
$('#redo').addEventListener('click', () => { if (!future.length) return; history.push(clone(working)); working = future.pop(); $('#inspector').hidden = true; persistDraft(); render(); });
$('#discard').addEventListener('click', () => {
  if (saving || mode !== 'planning') return;
  if (!confirm('Die offenen \u00c4nderungen f\u00fcr dieses Schiff verwerfen?')) return;
  commit(working.map((ship) => ship.id === selected ? clone(saved.ships.find((item) => item.id === selected)) : clone(ship)));
  $('#inspector').hidden = true;
  notify('\u00c4nderungen f\u00fcr dieses Schiff verworfen. Der aktuelle Plan ist unver\u00e4ndert.');
});
$('#save').addEventListener('click', async () => {
  if (saving || mode !== 'planning') return;
  const shipId = selected, before = clone(working);
  const pending = new Set(working.filter((ship) => ship.id !== shipId && shipDirtyCount(ship)).map((ship) => ship.id));
  saving = true;
  render();
  const controls = [...document.querySelectorAll('#stop-form input, #stop-form select, #stop-form button')];
  const disabled = controls.map((control) => control.disabled);
  controls.forEach((control) => { control.disabled = true; });
  try {
    const response = await fetch(`/api/ships/${shipId}/plan`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({revision: saved.revision, dataSignature: saved.dataSignature, ship: before.find((ship) => ship.id === shipId)})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Speichern fehlgeschlagen.');
    saved = result;
    working = saved.ships.map((ship) => clone(pending.has(ship.id) ? before.find((item) => item.id === ship.id) : ship));
    const accepted = saved.ships.find((ship) => ship.id === shipId);
    const rebase = (snapshot) => snapshot.map((ship) => ship.id === shipId ? clone(accepted) : ship);
    history = history.map(rebase).filter((snapshot) => JSON.stringify(snapshot) !== JSON.stringify(working));
    future = future.map(rebase).filter((snapshot) => JSON.stringify(snapshot) !== JSON.stringify(working));
    persistDraft();
    $('#inspector').hidden = true;
    notify(`Plan f\u00fcr ${accepted.name} \u00fcbernommen. Andere offene \u00c4nderungen bleiben erhalten.`);
  } catch (error) { notify(error.message, true); }
  finally { saving = false; controls.forEach((control, index) => { control.disabled = disabled[index]; }); render(); }
});
$('#export').addEventListener('click', () => {
  if (!saved) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify({ports: saved.ports, services: saved.services, ships: working, isDraft: !!dirtyCount()}, null, 2)], {type: 'application/json'}));
  const link = document.createElement('a');
  link.href = url; link.download = 'harborline-plan.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') $('#inspector').hidden = true;
  if (event.target.matches('input,select,textarea')) return;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); $(event.shiftKey ? '#redo' : '#undo').click(); }
});

async function initialize() {
  try {
    const response = await fetch('/api/plan');
    if (!response.ok) throw new Error('Fahrpl\u00e4ne konnten nicht geladen werden.');
    saved = await response.json();
    working = clone(saved.ships);
    try {
      const draft = JSON.parse(localStorage.getItem('harborline-draft') || 'null');
      if (draft?.revision === saved.revision && Array.isArray(draft.ships) && draft.ships.every((ship) => Array.isArray(ship.proformas) && ship.voyages)) {
        if (draft.dataSignature && draft.dataSignature !== saved.dataSignature) {
          const fresh = saved;
          if (Array.isArray(draft.baseShips)) saved = {...saved, dataSignature: draft.dataSignature, ships: draft.baseShips};
          notify('Die JSON-Dateien wurden extern ge\u00e4ndert. Dein Entwurf bleibt erhalten. Vor dem Aktualisieren bitte exportieren oder verwerfen.', true);
          dataChangeNotice = fresh.dataSignature;
        }
        working = draft.ships.map((ship) => ({...saved.ships.find((item) => item.id === ship.id), ...ship, maxSpeedKnots: ship.maxSpeedKnots ?? saved.ships.find((item) => item.id === ship.id)?.maxSpeedKnots ?? 20}));
        mode = 'planning';
        activeProforma = draft.activeProforma || 'initial';
        if (working.some((ship) => ship.id === draft.selected)) selected = draft.selected;
        if (!working.some((ship) => ship.id === selected)) selected = working[0].id;
        selectedService = working.find((ship) => ship.id === selected).serviceId;
        if (/^\d{4}-\d{2}-\d{2}$/.test(draft.activeDate || '')) activeDate = draft.activeDate;
        if (!dataChangeNotice) notify('Lokaler Entwurf wiederhergestellt.');
      } else if (draft) { notify('Ein \u00e4lterer lokaler Entwurf passt nicht zum aktuellen Plan. Er bleibt im Browser gespeichert.', true); }
    } catch { localStorage.removeItem('harborline-draft'); }
    $('#service-select').innerHTML = saved.services.map((service) => `<option value="${escapeHtml(service.id)}">${escapeHtml(service.id)}</option>`).join('');
    views = await (await fetch('/api/views')).json();
    let viewName = '';
    try { viewName = localStorage.getItem('harborline-view') || ''; } catch {}
    populateViews(viewName);
    if (views[viewName]) applyView(views[viewName]);
    render();
    icons();
  } catch (error) { $('#chart').innerHTML = `<div class="empty-error">${escapeHtml(error.message)} Bitte die Seite neu laden.</div>`; notify(error.message, true); }
}
initialize();

async function refreshData() {
  if (!saved || saving || refreshingData || activeDrag || !$('#inspector').hidden) return;
  refreshingData = true;
  try {
    const response = await fetch('/api/plan', {cache: 'no-store'});
    const next = await response.json();
    if (!response.ok) throw new Error(next.error || 'JSON-Daten konnten nicht geladen werden.');
    if (!Array.isArray(next.ships) || !next.ships.length) throw new Error('Keine g\u00fcltigen Schiffsdateien vorhanden.');
    dataLoadNotice = '';
    if (next.dataSignature === saved.dataSignature) return;
    const focused = document.activeElement;
    if (dirtyCount() || focused?.matches('input,select,textarea') || $('#view-options').open) {
      if (dataChangeNotice !== next.dataSignature) {
        notify('JSON-Dateien ge\u00e4ndert. Offene Entw\u00fcrfe und Eingaben werden nicht \u00fcberschrieben. Entwurf bei Bedarf exportieren oder verwerfen.', true);
        dataChangeNotice = next.dataSignature;
      }
      return;
    }
    const scroll = $('#chart-scroll'), left = scroll.scrollLeft, top = scroll.scrollTop;
    saved = next;
    working = clone(saved.ships);
    history = []; future = [];
    if (!working.some((ship) => ship.id === selected)) selected = working[0]?.id;
    if (!selected) throw new Error('Keine Schiffsdateien vorhanden.');
    selectedService = working.find((ship) => ship.id === selected).serviceId;
    $('#service-select').innerHTML = saved.services.filter((service) => working.some((ship) => ship.serviceId === service.id)).map((service) => `<option value="${escapeHtml(service.id)}">${escapeHtml(service.id)}</option>`).join('');
    render();
    scroll.scrollLeft = left; scroll.scrollTop = top;
    dataChangeNotice = '';
    notify('JSON-Daten aktualisiert.');
  } catch (error) {
    if (dataLoadNotice !== error.message) { notify(error.message, true); dataLoadNotice = error.message; }
  } finally { refreshingData = false; }
}
setInterval(refreshData, 5000);
globalThis.addEventListener('focus', refreshData);