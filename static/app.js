const $ = (selector) => document.querySelector(selector);
const DAY = 86400000;
const HOUR = 3600000;
const today = new Date();
let START = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()) - 10 * DAY;
const addMonths = (value, count) => {
  const date = new Date(value), last = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + count + 1, 0)).getUTCDate();
  return Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + count, Math.min(date.getUTCDate(), last));
};
let END = addMonths(START + 10 * DAY, 6) + DAY;
const calendarDays = () => Math.ceil((END - START) / DAY);
function shiftCalendar(start) { const duration = END - START; START = start; END = START + duration; }
const clone = (value) => structuredClone(value);
const instant = (value) => Date.parse(value + 'Z');
const iso = (value) => new Date(value).toISOString().slice(0, 16);
const dateLabel = (value, options = {}) => new Intl.DateTimeFormat('de-DE', {timeZone: 'UTC', ...options}).format(new Date(value));
const shortDate = (value) => dateLabel(value, {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'});
const roundedHours = (value) => Number(value.toFixed(2));
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
let saved, working, selected = null, dayWidth = 64, history = [], future = [], editing = null, problems = [];
let toastTimer, saving = false;
let activeDate = null, selectedService = null, mode = 'planning', activeProforma = null;
let proformaDraft = null, proformaDirty = false, proformaIsNew = false;
let proformaTemplate = true;
let collapsed = new Set(), hiddenBerths = new Set(), views = {}, activeDrag = false;
let compareProforma = false;
let refreshingData = false, dataChangeNotice = '', dataLoadNotice = '';
let rotating = false;
let harborOverview = false, selectedPorts = new Set(), addingPort = null;
let addingPortBusy = false;
let importPreview = null, importChoices = {}, importing = false;
let importFingerprint = '';
let importExcludedShips = new Set();
let calculatingImport = false, importPreviewQueued = false;
const icons = () => { if (globalThis.lucide) lucide.createIcons(); };
const serviceFor = (ship) => saved.services.find((service) => service.id === ship.serviceId);
const proformasFor = (ship) => serviceFor(ship)?.proformas || ship.proformas || [];
const assignmentsFor = (ship) => ship.proformaAssignments || (ship.proformas || []).map((item) => ({proformaId: item.id, validFrom: item.validFrom, offsetWeeks: 0}));
const serviceProforma = (ship, id) => proformasFor(ship).find((item) => item.id === id);
const dayInstant = (value) => Date.parse(value.slice(0, 10) + 'T00:00Z');
const localToday = () => {
  const date = new Date();
  return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
};
function jumpToToday() {
  const day = localToday();
  if (day < START || day >= END) {
    notify('Das gewaehlte Zeitfenster enthaelt Heute nicht.', true);
    return;
  }
  $('#chart-scroll').scrollTo({left: Math.max(0, (day - START) / DAY * dayWidth - 36), behavior: 'smooth'});
}
function proformaStops(ship) {
  const version = proformaDraft?.id === activeProforma ? proformaDraft : serviceProforma(ship, activeProforma);
  if (!version) return [];
  const assignment = assignmentsFor(ship).filter((item) => item.proformaId === activeProforma).sort((left, right) => left.validFrom.localeCompare(right.validFrom)).at(-1);
  if (!proformaTemplate && !assignment) return [];
  const delta = proformaTemplate ? 0 : assignment.offsetWeeks * 7 * DAY;
  return version.stops.map((stop) => ({...stop, arrival: iso(instant(stop.arrival) + delta), departure: iso(instant(stop.departure) + delta)}));
}
function resolveVoyage(ship, date) {
  const day = date.slice(0, 10);
  if (ship.voyages[day]) return {key: day, source: 'actual', ...ship.voyages[day]};
  const assignments = assignmentsFor(ship).filter((item) => item.validFrom <= day).sort((left, right) => left.validFrom.localeCompare(right.validFrom));
  if (!assignments.length) {
    const actuals = Object.entries(ship.voyages).filter(([key, voyage]) => key <= day && voyage.stops.some((stop) => stop.departure.slice(0, 10) >= day));
    if (!actuals.length) return null;
    const [key, voyage] = actuals.sort(([left], [right]) => left.localeCompare(right)).at(-1);
    return {key, source: 'actual', ...voyage};
  }
  const assignment = assignments.at(-1), version = serviceProforma(ship, assignment.proformaId);
  if (!version) return null;
  const period = version.repeatWeeks * 7 * DAY, anchor = instant(version.stops[0].arrival) + assignment.offsetWeeks * 7 * DAY;
  let cycle = Math.floor((dayInstant(day) - dayInstant(iso(anchor))) / period);
  if (iso(anchor + cycle * period).slice(0, 10) < assignment.validFrom) cycle++;
  const key = iso(anchor + cycle * period).slice(0, 10);
  if (assignmentsFor(ship).some((item) => item.validFrom > assignment.validFrom && item.validFrom <= key)) return null;
  if (ship.voyages[key]) return {key, source: 'actual', ...ship.voyages[key]};
  const stops = clone(version.stops);
  for (const stop of stops) for (const field of ['arrival', 'departure']) stop[field] = iso(instant(stop[field]) + cycle * period + assignment.offsetWeeks * 7 * DAY);
  return {key, source: 'proforma', proformaId: version.id, stops};
}
function stopsFor(ship, date = activeDate, editable = false) {
  if (mode === 'proformas') return proformaStops(ship);
  const voyage = displayVoyage(ship, date);
  if (!voyage) return [];
  if (editable && !ship.voyages[voyage.key]) ship.voyages[voyage.key] = {proformaId: voyage.proformaId, stops: voyage.stops};
  return editable ? ship.voyages[voyage.key].stops : voyage.stops;
}
function displayVoyage(ship, date) {
  let voyage = resolveVoyage(ship, date);
  for (let attempt = 0; voyage && Math.max(...voyage.stops.map((stop) => instant(stop.departure))) < START && attempt < 200; attempt++) {
     const version = serviceProforma(ship, voyage.proformaId);
    if (!version) return null;
    voyage = resolveVoyage(ship, iso(dayInstant(voyage.key) + version.repeatWeeks * 7 * DAY).slice(0, 10));
  }
  return voyage;
}
const shipById = (id, date = activeDate) => { const ship = working.find((item) => item.id === id); return {...ship, stops: stopsFor(ship, date)}; };
const baselineShip = (id, date = activeDate) => { const ship = saved.ships.find((item) => item.id === id); return {...ship, stops: stopsFor(ship, date)}; };
const changed = (shipId, stop, date = activeDate) => JSON.stringify(stop) !== JSON.stringify(baselineShip(shipId, date).stops.find((old) => old.id === stop.id));
const shipDirtyCount = (ship) => Number(JSON.stringify(ship) !== JSON.stringify(saved.ships.find((item) => item.id === ship.id)));
const dirtyCount = () => working.reduce((count, ship) => count + shipDirtyCount(ship), 0);
const routePorts = () => harborOverview
  ? [...selectedPorts].map((id) => saved.ports.find((port) => port.id === id)).filter(Boolean)
  : [...new Set(shipById(selected).stops.map((stop) => stop.portId))].map((id) => saved.ports.find((port) => port.id === id));
function portLabel(port) {
  return saved.ports.filter((item) => item.name === port.name).length > 1 ? `${port.name} (${port.id})` : port.name;
}
function renderServiceOptions() {
  $('#service-select').innerHTML = '<option value="__ports__">Hafen\u00fcbersicht</option>' + saved.services.filter((service) => working.some((ship) => ship.serviceId === service.id)).map((service) => `<option value="${escapeHtml(service.id)}">${escapeHtml(service.id)}</option>`).join('');
  const previous = $('#import-service').value;
  $('#import-service').innerHTML = saved.services.filter((service) => working.some((ship) => ship.serviceId === service.id)).map((service) => `<option value="${escapeHtml(service.id)}">${escapeHtml(service.id)}</option>`).join('');
  if ([...$('#import-service').options].some((option) => option.value === previous)) $('#import-service').value = previous;
}
function shipColor(ship) {
  return serviceFor(ship)?.color || '#278ba9';
}

function minimumTransit(ship, origin, destination) {
  const from = saved.ports.find((port) => port.id === origin), to = saved.ports.find((port) => port.id === destination);
  const distance = origin === destination ? 0 : from?.distancesNm?.[destination] ?? to?.distancesNm?.[origin];
  if (!Number.isFinite(distance) || distance < 0) throw new Error(`Entfernung zwischen ${origin} und ${destination} fehlt oder ist ungueltig.`);
  const speed = ship.maxSpeedKnots;
  if (!Number.isFinite(speed) || speed <= 0) throw new Error(`Maximalgeschwindigkeit fuer ${ship.name} fehlt oder ist ungueltig.`);
  return {distance, speed, hours: distance / speed};
}

function proformaFor(ship, voyage) {
  return resolveVoyage({...ship, voyages: {}}, voyage.key);
}

function referenceHtml(ship, actual, voyage, summary = false) {
  if (!compareProforma || harborOverview || mode !== 'planning' || ship.serviceId !== selectedService) return '';
  const plan = proformaFor(ship, voyage)?.stops.find((stop) => stop.id === actual.id || (!actual.adhoc && stop.portId === actual.portId));
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
  if (!compareProforma || harborOverview || mode !== 'planning') return;
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
    if (dirtyCount()) localStorage.setItem(storageKey('harborline-draft'), JSON.stringify({dataSignature: saved.dataSignature, baseShips: saved.ships, ships: working, mode, activeProforma, selected, activeDate}));
    else localStorage.removeItem(storageKey('harborline-draft'));
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
  const proforma = mode === 'proformas' || !ship.voyages[voyageDate];
  const classes = ['bar', ghost ? 'ghost' : !harborOverview && ship.id === selected ? 'selected' : '', dirty ? 'draft' : '', proforma && !ghost ? 'proforma-pattern' : ''].join(' ');
  const title = `${ship.name}${ghost ? ' / Bisher gespeichert' : ''}\n${shortDate(instant(stop.arrival))} - ${shortDate(instant(stop.departure))}\nLiegeplatz ${stop.berth}${dirty ? '\nUngespeicherter Entwurf' : ''}`;
  return `<div class="${classes}" style="--ship-color:${shipColor(ship)};left:${left}px;width:${Math.max(width, 6)}px" ${ghost ? '' : `data-ship="${ship.id}" data-stop="${stop.id}" data-voyage="${voyageDate}" tabindex="0" role="button" aria-label="${escapeHtml(title)}"`} title="${escapeHtml(title)}">${escapeHtml(ship.name)}${ghost || harborOverview ? '' : '<span class="resize-handle" title="Abfahrt verschieben"></span>'}</div>`;
}

function visibleVoyages(ship) {
  if (mode === 'proformas') return ship.id === selected && stopsFor(ship).length ? [{key: stopsFor(ship)[0].arrival.slice(0, 10), stops: stopsFor(ship)}] : [];
  const result = new Map();
  for (const assignment of assignmentsFor(ship)) {
    const version = serviceProforma(ship, assignment.proformaId);
    if (!version) continue;
    const period = version.repeatWeeks * 7 * DAY, anchor = instant(version.stops[0].arrival) + assignment.offsetWeeks * 7 * DAY;
    let cycle = Math.floor((START - anchor) / period) - 1;
    while (anchor + cycle * period < END) {
      const key = iso(anchor + cycle * period).slice(0, 10);
      if (key >= assignment.validFrom) {
        const voyage = resolveVoyage(ship, key);
        if (voyage?.key === key) result.set(key, voyage);
      }
      cycle++;
    }
  }
  for (const [key, voyage] of Object.entries(ship.voyages)) result.set(key, {...voyage, key, source: 'actual'});
  return [...result.values()].filter((voyage) => Math.min(...voyage.stops.map((stop) => instant(stop.arrival))) < END && Math.max(...voyage.stops.map((stop) => instant(stop.departure))) >= START);
}

function transitRow(position, port, nextPort, voyages) {
  const ship = working.find((item) => item.id === selected);
  const todayStart = localToday();
  let content = todayStart >= START && todayStart < END ? `<span class="today-band" style="left:${(todayStart - START) / DAY * dayWidth}px;width:${dayWidth}px"></span>` : '';
  let needsRotation = false;
  for (const voyage of voyages) {
    for (const [index, stay] of voyage.stops.entries()) {
    if (stay.portId !== port.id) continue;
    const next = voyage.stops[index + 1];
    const duration = (instant(stay.departure) - instant(stay.arrival)) / HOUR;
    const left = (instant(stay.arrival) - START) / DAY * dayWidth;
    const width = duration / 24 * dayWidth;
    const label = mode === 'proformas' && proformaTemplate ? serviceProforma(ship, activeProforma)?.name || ship.name : ship.name;
    content += `<button type="button" class="stay-box ${voyage.source === 'proforma' || mode === 'proformas' ? 'proforma-pattern' : ''}" data-overview-stop="${stay.id}" data-voyage="${voyage.key}" style="left:${left}px;width:${Math.max(width, 6)}px" title="${escapeHtml(label)}\nLiegezeit: ${roundedHours(duration)} h"><strong>${escapeHtml(label)}</strong><span>Liegezeit: ${roundedHours(duration)} h</span></button>`;
    content += referenceHtml(ship, stay, voyage, true);
    if (next) {
      const gap = (instant(next.arrival) - instant(stay.departure)) / HOUR;
      const minimum = minimumTransit(ship, stay.portId, next.portId);
      const destination = saved.ports.find((item) => item.id === next.portId);
      const rotationButton = (gap < 0 || next.transitMinutes < 0) && mode === 'planning'
        ? `<button type="button" class="change-rotation" data-change-rotation="${voyage.key}" data-rotation-ship="${ship.id}">Change Rotation</button>` : '';
      if (rotationButton) needsRotation = true;
      const transitLeft = (instant(stay.departure) - START) / DAY * dayWidth;
      content += `<form class="transit-editor" data-transit="${next.id}" data-voyage="${voyage.key}" style="left:${transitLeft}px"><span>${escapeHtml(port.name)} &rarr; ${escapeHtml(destination.name)}</span><label><input type="number" min="0" max="10000" step="0.01" value="${roundedHours(next.transitMinutes / 60)}" aria-label="Transit nach ${escapeHtml(destination.name)} in Stunden" required ${harborOverview ? 'disabled' : ''}> h</label><button type="submit" title="Transit anwenden und Ankunft neu berechnen" aria-label="Transit anwenden" ${harborOverview ? 'hidden' : ''}>&#10003;</button><small class="${gap < minimum.hours ? 'negative-gap' : ''}">${roundedHours(gap)} h verf\u00fcgbar / min. ${roundedHours(minimum.hours)} h (${minimum.distance} sm / ${minimum.speed} kn)</small>${rotationButton}</form>`;
    }
    }
  }
  return `<div class="transit-row ${needsRotation ? 'rotation-needed' : ''}"><div class="transit-label">${nextPort ? `Transit ${position + 1}` : 'Ankunft / Liegezeit'}</div><div class="transit-track" style="width:${calendarDays() * dayWidth}px">${content}</div></div>`;
}

function renderChart() {
  const DAYS = calendarDays();
  const chart = $('#chart');
  chart.style.width = `calc(var(--label) + ${DAYS * dayWidth}px)`;
  chart.style.setProperty('--day', `${dayWidth}px`);
  chart.classList.toggle('compare-proforma', compareProforma && !harborOverview && mode === 'planning');
  let days = '';
  let weekendBands = '';
  const todayStart = localToday();
  for (let index = 0; index < DAYS; index++) {
    const date = new Date(START + index * DAY);
    const weekend = [0, 6].includes(date.getUTCDay());
    const isToday = date.getTime() === todayStart;
    const hours = dayWidth >= 240 ? `<div class="hour-labels">${Array.from({length: 8}, (_, hour) => `<span>${String(hour * 3).padStart(2, '0')}:00</span>`).join('')}</div>` : '';
    days += `<div class="day ${isToday ? 'today' : ''} ${weekend ? 'weekend' : ''} ${date.getUTCDay() === 1 ? 'week-start' : ''}" ${isToday ? 'aria-current="date"' : ''}>${dateLabel(date, {day: '2-digit', month: '2-digit'})}<small>${dateLabel(date, {weekday: 'short'})}</small>${hours}</div>`;
    if (weekend) weekendBands += `<span class="weekend-band" style="left:${index * dayWidth}px;width:${dayWidth}px"></span>`;
  }
  if (todayStart >= START && todayStart < END) weekendBands += `<span class="today-band" style="left:${(todayStart - START) / DAY * dayWidth}px;width:${dayWidth}px"></span>`;
  let html = `<div class="time-header"><div class="time-corner">HAFEN / LIEGEPLATZ</div><div class="time-days">${days}</div></div>`;
  const route = shipById(selected).stops;
  const selectedVoyages = visibleVoyages(working.find((ship) => ship.id === selected));
  const ports = routePorts();
  const chartShips = mode === 'proformas' ? working.filter((item) => item.id === selected) : working;
  for (const [position, port] of ports.entries()) {
    if (position && !harborOverview) {
      html += transitRow(position - 1, ports[position - 1], port, selectedVoyages);
    }
    const canInsert = route.some((stop) => stop.portId === port.id);
    const addButton = !harborOverview && mode === 'planning' ? `<button type="button" class="add-port-button" data-add-port="${port.id}" ${canInsert ? '' : 'disabled'} title="Zus\u00e4tzlichen Hafen vor diesem Aufenthalt einf\u00fcgen">+ Hafen hinzuf\u00fcgen</button>` : '';
    html += `<div class="port-heading"><div class="port-heading-content"><button class="port-label port-toggle" data-collapse="${port.id}" aria-expanded="${!collapsed.has(port.id)}" title="Hafen ein- oder ausklappen"><span class="chevron ${collapsed.has(port.id) ? 'closed' : ''}">&#9662;</span>${escapeHtml(port.name)}</button><div class="port-note">${port.berths} LIEGEPL${port.berths === 1 ? 'ATZ' : '&Auml;TZE'}</div>${addButton}</div></div>`;
    if (collapsed.has(port.id)) continue;
    for (let berth = 1; berth <= port.berths; berth++) {
      if (hiddenBerths.has(`${port.id}:${berth}`)) continue;
      let bars = '';
      for (const raw of chartShips) {
        for (const voyage of visibleVoyages(raw)) {
        const ship = {...raw, name: mode === 'proformas' && proformaTemplate ? serviceProforma(raw, activeProforma)?.name || raw.name : raw.name, stops: voyage.stops};
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
  if (ports.length && !harborOverview) html += transitRow(ports.length - 1, ports.at(-1), null, selectedVoyages);
  if (!ports.length && harborOverview) html += '<div class="empty-ports">Keine H\u00e4fen ausgew\u00e4hlt</div>';
  if (!ports.length && !harborOverview) html += '<div class="empty-ports">Kein Fahrplan f\u00fcr diesen Zeitraum vorhanden</div>';
  chart.innerHTML = html;
  chart.classList.toggle('hourly', dayWidth >= 240);
  chart.classList.toggle('proforma-readonly', mode === 'proformas');
  $('#visible-range').textContent = `${dateLabel(START, {day: '2-digit', month: '2-digit', year: 'numeric'})} - ${dateLabel(START + (DAYS - 1) * DAY, {day: '2-digit', month: '2-digit', year: 'numeric'})}`;
  $('#timeline-start').value = iso(START).slice(0, 10);
  $('#timeline-end').value = iso(END - DAY).slice(0, 10);
  renderConnections();
}

function renderSidebar() {
  const legend = $('#service-legend');
  legend.replaceChildren();
  for (const service of saved.services.filter((item) => working.some((ship) => ship.serviceId === item.id))) {
    const color = service.color || '#278ba9';
    const entry = document.createElement('span');
    entry.className = 'configured-service';
    const swatch = document.createElement('b');
    swatch.className = 'swatch';
    swatch.style.backgroundColor = color;
    entry.append(swatch, document.createTextNode(service.id));
    legend.append(entry);
  }
  $('#fleet-title').textContent = harborOverview ? 'H\u00e4fen' : 'Schiffe';
  $('#fleet').classList.toggle('harbor-list', harborOverview);
  $('.route-section').hidden = harborOverview;
  $('#fleet').innerHTML = harborOverview ? saved.ports.map((port) => `<label class="port-choice"><input type="checkbox" data-pick-port="${port.id}" ${selectedPorts.has(port.id) ? 'checked' : ''}><span>${escapeHtml(portLabel(port))}</span><small>${port.berths} LP</small></label>`).join('') : (mode === 'proformas' ? `<button type="button" class="fleet-button ${proformaTemplate ? 'active' : ''}" data-template>Proforma ohne Wochenversatz</button>` : '') + working.filter((ship) => ship.serviceId === selectedService).map((ship) => {
    const count = shipDirtyCount(ship);
    return `<button class="fleet-button ${ship.id === selected && !(mode === 'proformas' && proformaTemplate) ? 'active' : ''}" data-select="${ship.id}" style="--ship-color:${shipColor(ship)}"><span class="vessel-dot"></span><span>${escapeHtml(ship.name)}<small class="fleet-service">${ship.serviceId}${mode === 'proformas' && !assignmentsFor(ship).some((item) => item.proformaId === activeProforma) ? ' / Keine Zuordnung' : ''}</small></span>${count ? '<span class="vessel-draft">Pending</span>' : ''}</button>`;
  }).join('');
  const ship = shipById(selected);
  $('#route').innerHTML = ship.stops.map((stop, index) => `<div class="route-stop"><button data-detail="${stop.id}">${escapeHtml(saved.ports.find((port) => port.id === stop.portId).name)}</button><div class="route-time">${shortDate(instant(stop.arrival))}</div>${index ? `<button class="transit" data-detail="${stop.id}" title="Transit bearbeiten">${roundedHours(stop.transitMinutes / 60)} h Transit</button>` : ''}</div>`).join('');
  const visibleProblems = [...new Map(problems.map((item) => [`${item.isNew}:${item.message}`, item])).values()];
  $('#route-count').textContent = `${ship.stops.length} H\u00e4fen`;
  $('#fleet-count').textContent = harborOverview ? `${selectedPorts.size} / ${saved.ports.length}` : String(working.filter((ship) => ship.serviceId === selectedService).length).padStart(2, '0');
  $('#conflict-count').textContent = visibleProblems.length ? `${visibleProblems.length} HINWEIS${visibleProblems.length > 1 ? 'E' : ''}` : 'OK';
  $('#conflict-count').classList.toggle('error', visibleProblems.some((item) => item.isNew));
  $('#conflicts').innerHTML = visibleProblems.length ? visibleProblems.map((item) => `<div class="conflict-item">${item.isNew ? 'Neu' : 'Bestand'}<br>${escapeHtml(item.message)}</div>`).join('') : '<p class="conflict-good">Keine Doppelbelegungen.<br>Transitzeiten eingehalten.</p>';
}

function render() {
  const isImport = mode === 'import';
  const isMaster = mode === 'fleet' || mode === 'ports';
  $('#master-panel').hidden = !isMaster;
  $('#import-panel').hidden = !isImport;
  $('.toolbar').hidden = isImport || isMaster;
  $('.view-toolbar').hidden = isImport || isMaster;
  $('.workspace').hidden = isImport || isMaster;
  $('#tab-import').classList.toggle('nav-active', isImport);
  $('#tab-fleet').classList.toggle('nav-active', mode === 'fleet');
  $('#tab-ports').classList.toggle('nav-active', mode === 'ports');
  if (isMaster) {
    $('#proforma-toolbar').hidden = true;
    for (const id of ['#tab-planning', '#tab-proformas', '#tab-import']) $(id).classList.remove('nav-active');
    renderMasterPanel(mode);
    return;
  }
  if (isImport) {
    $('#proforma-toolbar').hidden = true;
    $('#tab-planning').classList.remove('nav-active');
    $('#tab-proformas').classList.remove('nav-active');
    updateImportApply();
    return;
  }
  const selectedShip = working.find((ship) => ship.id === selected);
  if (!selectedShip) { $('#chart').innerHTML = '<div class="empty-ports">Keine Schiffe vorhanden</div>'; return; }
  selectedService = selectedShip.serviceId;
  if (!proformaIsNew && !proformasFor(selectedShip).some((version) => version.id === activeProforma)) activeProforma = assignmentsFor(selectedShip)[0]?.proformaId || proformasFor(selectedShip)[0]?.id || null;
  problems = findProblems();
  renderChart();
  renderSidebar();
  const count = dirtyCount();
  $('#service-select').value = harborOverview ? '__ports__' : selectedService;
  $('#draft-count').textContent = shipDirtyCount(selectedShip);
  $('#undo').disabled = !history.length || saving || mode !== 'planning';
  $('#redo').disabled = !future.length || saving || mode !== 'planning';
  $('#discard').disabled = !shipDirtyCount(selectedShip) || saving || mode !== 'planning';
  const selectedOnly = saved.ships.map((ship) => ship.id === selected ? selectedShip : ship);
  const oldIssues = new Map(findProblemsFor(saved.ships).map((item) => [item.key, item.severity]));
  const newIssues = findProblemsFor(selectedOnly).filter((item) => item.severity > (oldIssues.get(item.key) || 0));
  $('#save').disabled = !shipDirtyCount(selectedShip) || !!newIssues.length || saving;
  $('#save').hidden = mode !== 'planning' || harborOverview;
  $('#undo').hidden = $('#redo').hidden = $('#discard').hidden = mode !== 'planning' || harborOverview;
  $('#cascade').closest('label').hidden = mode !== 'planning' || harborOverview;
  $('#compare-proforma').closest('label').hidden = mode !== 'planning' || harborOverview;
  $('#focus').hidden = harborOverview;
  $('#compare-proforma').checked = compareProforma;
  $('#status').textContent = mode === 'proformas' ? proformaDirty ? 'Proforma-Entwurf' : 'Dienst-Proforma' : newIssues.length ? `${newIssues.length} Konflikte bei Einzel\u00fcbernahme` : count ? `${count} Schiffe mit offenen \u00c4nderungen` : 'Aktueller Plan';
  $('#voyage').value = activeDate;
  const rawSelected = working.find((ship) => ship.id === selected);
  const resolved = displayVoyage(rawSelected, activeDate);
  $('#service-info').textContent = harborOverview ? 'Alle Dienste' : mode === 'proformas' ? 'PROFORMA' : resolved ? `${resolved.source === 'actual' ? 'Fahrplan' : 'Proforma'} / ${resolved.key}` : 'Noch kein Fahrplan f\u00fcr dieses Datum';
  $('#reset-voyage').hidden = mode !== 'planning' || harborOverview || resolved?.source !== 'actual';
  $('#reset-voyage').disabled = saving;
  $('#save-label').textContent = 'Plan f\u00fcr dieses Schiff \u00fcbernehmen';
  $('#tab-planning').classList.toggle('nav-active', mode === 'planning');
  $('#tab-proformas').classList.toggle('nav-active', mode === 'proformas');
  $('#proforma-toolbar').hidden = mode !== 'proformas';
  $('#voyage-control').hidden = mode === 'proformas' || harborOverview;
  renderProformaControls();
  $('#zoom').value = dayWidth;
  $('#stop-count').textContent = working.reduce((count, raw) => count + visibleVoyages(raw).reduce((total, voyage) => total + voyage.stops.filter((stop) => routePorts().some((port) => port.id === stop.portId)).length, 0), 0);
  renderBerthOptions();
}

function selectShip(id, focus = false) {
  if (mode === 'proformas') proformaTemplate = false;
  selected = id;
  const selectedShip = working.find((ship) => ship.id === id);
  selectedService = selectedShip.serviceId;
  if (mode === 'planning' && !resolveVoyage(selectedShip, activeDate) && !assignmentsFor(selectedShip).length) {
    const actuals = Object.entries(selectedShip.voyages).sort(([left], [right]) => left.localeCompare(right));
    const visible = visibleVoyages(selectedShip).sort((left, right) => left.key.localeCompare(right.key));
    activeDate = visible[0]?.key || actuals[0]?.[0] || activeDate;
  }
  if (!proformasFor(working.find((ship) => ship.id === id)).some((item) => item.id === activeProforma)) activeProforma = assignmentsFor(working.find((ship) => ship.id === id))[0]?.proformaId || proformasFor(working.find((ship) => ship.id === id))[0]?.id || null;
  if (mode === 'proformas') { proformaDraft = clone(serviceProforma(working.find((ship) => ship.id === id), activeProforma)); proformaDirty = false; proformaIsNew = false; }
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
  if (mode === 'planning' && !harborOverview) {
    selected = shipId;
    activeDate = date;
    render();
  }
  editing = {shipId, stopId, date};
  const ship = shipById(shipId, date), stop = ship.stops.find((item) => item.id === stopId);
  const port = saved.ports.find((item) => item.id === stop.portId);
  $('#detail-ship').textContent = `${ship.name} / ${ship.serviceId} / ${mode === 'proformas' ? 'Proforma' : date}`;
  $('#detail-port').textContent = port.name;
  $('#detail-berth').innerHTML = Array.from({length: port.berths}, (_, index) => `<option value="${index + 1}">Liegeplatz ${index + 1}</option>`).join('');
  $('#detail-berth').value = stop.berth;
  $('#detail-arrival').value = stop.arrival;
  $('#detail-departure').value = stop.departure;
  $('#detail-transit').value = roundedHours(stop.transitMinutes / 60);
  const first = ship.stops[0].id === stopId;
  $('#detail-transit').disabled = first;
  $('#recalculate').disabled = first;
  $('#recalculate').checked = false;
  $('#detail-error').textContent = '';
  const readOnly = harborOverview || mode === 'proformas';
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
  $('#proforma-service').innerHTML = saved.services.map((service) => `<option value="${escapeHtml(service.id)}">${escapeHtml(service.id)}</option>`).join('');
  $('#proforma-service').value = ship.serviceId;
  const versions = proformasFor(ship);
  const version = versions.find((item) => item.id === activeProforma) || (proformaIsNew ? proformaDraft : versions[0]);
  if (!version) {
    activeProforma = null;
    $('#proforma-select').innerHTML = '<option>Keine Proforma vorhanden</option>';
    for (const id of ['#proforma-name', '#proforma-start', '#proforma-weeks']) $(id).value = '';
    proformaDraft = null; proformaDirty = false; proformaIsNew = false;
    return;
  }
  activeProforma = version.id;
  if (!proformaDraft || proformaDraft.id !== activeProforma) { proformaDraft = clone(version); proformaDirty = false; proformaIsNew = false; }
  $('#proforma-select').innerHTML = [...versions, ...(proformaIsNew ? [proformaDraft] : [])].sort((left, right) => left.validFrom.localeCompare(right.validFrom)).map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} / ab ${item.validFrom}</option>`).join('');
  $('#proforma-select').value = version.id;
  $('#proforma-name').value = proformaDraft.name;
  $('#proforma-start').value = proformaDraft.validFrom;
  $('#proforma-weeks').value = proformaDraft.repeatWeeks;
  $('#proforma-save').disabled = !proformaDirty;
  $('#proforma-cancel').disabled = !proformaDirty;
}

function switchMode(nextMode) {
  if (saving) return;
  if (mode === nextMode) return;
  if (mode === 'proformas' && proformaDirty && !confirm('Ungespeicherte Proforma-Aenderungen verwerfen?')) return;
  if (mode === 'proformas') { proformaDirty = false; proformaDraft = null; proformaIsNew = false; }
  if (typeof masterDataDirty !== 'undefined' && masterDataDirty && !confirm('Ungespeicherte Stammdaten verwerfen?')) return;
  if (typeof masterDataDirty !== 'undefined') masterDataDirty = false;
  mode = nextMode;
  if (nextMode === 'proformas') { harborOverview = false; proformaTemplate = true; }
  $('#inspector').hidden = true;
  render();
  if (nextMode === 'planning' || nextMode === 'proformas') focusShip();
}
$('#tab-planning').addEventListener('click', () => switchMode('planning'));
$('#tab-proformas').addEventListener('click', () => switchMode('proformas'));
$('#tab-import').addEventListener('click', () => switchMode('import'));
$('#proforma-select').addEventListener('change', (event) => {
  if (proformaDirty && !confirm('Ungespeicherte Proforma-Aenderungen verwerfen?')) { event.target.value = activeProforma; return; }
  activeProforma = event.target.value;
  proformaDraft = clone(serviceProforma(working.find((item) => item.id === selected), activeProforma));
  proformaDirty = false; proformaIsNew = false;
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
  if (!config || !Array.isArray(config.collapsed) || !Array.isArray(config.hiddenBerths)
      || !Number.isFinite(config.dayWidth) || config.dayWidth < 16 || config.dayWidth > 1200
      || !Number.isFinite(instant(config.start || ''))
      || (config.end && dayInstant(config.end) < dayInstant(config.start))) {
    notify('Die gespeicherte Ansicht ist ung\u00fcltig.', true);
    return;
  }
  if (!working.some((ship) => ship.id === config.selected)) {
    notify('Das Schiff dieser gespeicherten Ansicht ist nicht mehr vorhanden.', true);
    $('#view-select').value = '';
    return;
  }
  collapsed = new Set(config.collapsed);
  hiddenBerths = new Set(config.hiddenBerths);
  dayWidth = config.dayWidth;
  compareProforma = config.compareProforma === true;
  harborOverview = config.harborOverview === true;
  selectedPorts = new Set((config.selectedPorts || []).filter((id) => saved.ports.some((port) => port.id === id)));
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
  const addPort = event.target.closest('[data-add-port]');
  if (addPort) { openAddPort(addPort.dataset.addPort); return; }
  const rotation = event.target.closest('[data-change-rotation]');
  if (rotation) { applyRotation(rotation); return; }
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

function openAddPort(portId) {
  if (saving || mode !== 'planning' || harborOverview) return;
  const ship = working.find((item) => item.id === selected), voyage = displayVoyage(ship, activeDate);
  if (!voyage) return;
  const eligible = voyage.stops.filter((stop) => stop.portId === portId);
  if (!eligible.length) { notify('Kein Aufenthalt in diesem Hafen vorhanden.', true); return; }
  addingPort = {shipId: ship.id, voyageDate: voyage.key};
  $('#add-port-context').textContent = `${ship.name} / Reise ${voyage.key}`;
  $('#add-port-before').innerHTML = eligible.map((stop) => `<option value="${escapeHtml(stop.id)}">${escapeHtml(saved.ports.find((port) => port.id === stop.portId).name)} / ${shortDate(instant(stop.arrival))}</option>`).join('');
  $('#add-port-choice').innerHTML = saved.ports.map((port) => `<option value="${escapeHtml(port.id)}">${escapeHtml(portLabel(port))}</option>`).join('');
  const defaultPort = saved.ports.find((port) => !voyage.stops.some((stop) => stop.portId === port.id)) || saved.ports[0];
  $('#add-port-choice').value = defaultPort.id;
  $('#add-port-error').textContent = '';
  $('#add-port-dialog').showModal();
}

$('#cancel-add-port').addEventListener('click', () => $('#add-port-dialog').close());
$('#add-port-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!addingPort || saving || addingPortBusy || mode !== 'planning' || harborOverview) return;
  const {shipId, voyageDate} = addingPort;
  const ship = working.find((item) => item.id === shipId), voyage = resolveVoyage(ship, voyageDate);
  if (!voyage) return;
  const before = JSON.stringify(working), ids = new Set(voyage.stops.map((stop) => stop.id));
  addingPortBusy = true;
  $('#confirm-add-port').disabled = true;
  $('#add-port-error').textContent = '';
  try {
    const response = await fetch(`/api/ships/${encodeURIComponent(shipId)}/adhoc-stop`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({dataSignature: saved.dataSignature, voyageDate, stops: voyage.stops, beforeStopId: $('#add-port-before').value, portId: $('#add-port-choice').value})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Hafen konnte nicht eingef\u00fcgt werden.');
    if (before !== JSON.stringify(working)) throw new Error('Der Entwurf wurde inzwischen ge\u00e4ndert. Bitte erneut einf\u00fcgen.');
    const next = clone(working), updated = next.find((item) => item.id === shipId);
    updated.voyages[voyageDate] = {proformaId: result.proformaId, stops: result.stops};
    selected = shipId; activeDate = voyageDate;
    $('#add-port-dialog').close();
    commit(next);
    const added = result.stops.find((stop) => !ids.has(stop.id));
    if (added) {
      collapsed.delete(added.portId);
      hiddenBerths.delete(`${added.portId}:${added.berth}`);
      renderChart();
      $('#chart-scroll').scrollLeft = Math.max(0, (instant(added.arrival) - START) / DAY * dayWidth - 70);
    }
    notify('Hafen nur in dieser Reise als Entwurf eingef\u00fcgt. Zeiten und Konflikte k\u00f6nnen jetzt angepasst werden.');
  } catch (error) { $('#add-port-error').textContent = error.message; }
  finally { addingPortBusy = false; $('#confirm-add-port').disabled = false; }
});

async function applyRotation(button) {
  if (saving || rotating || mode !== 'planning') return;
  const shipId = button.dataset.rotationShip, key = button.dataset.changeRotation;
  const ship = working.find((item) => item.id === shipId), voyage = resolveVoyage(ship, key);
  if (!voyage) return;
  const before = JSON.stringify(working);
  rotating = true;
  button.disabled = true;
  try {
    const response = await fetch(`/api/ships/${encodeURIComponent(shipId)}/rotation`, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({dataSignature: saved.dataSignature, voyageDate: key, stops: voyage.stops})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Change Rotation konnte nicht berechnet werden.');
    if (before !== JSON.stringify(working) || mode !== 'planning') throw new Error('Der Entwurf wurde inzwischen ge\u00e4ndert. Bitte Change Rotation erneut ausf\u00fchren.');
    const next = clone(working), updated = next.find((item) => item.id === shipId);
    updated.voyages[key] = {proformaId: result.proformaId, stops: result.stops};
    selected = shipId;
    activeDate = key;
    $('#inspector').hidden = true;
    commit(next);
    notify('Neue Hafenfolge als Entwurf \u00fcbernommen. Aufenthaltszeiten sind unver\u00e4ndert.');
  } catch (error) { notify(error.message, true); }
  finally { rotating = false; button.disabled = false; }
}

$('#chart').addEventListener('submit', (event) => {
  const form = event.target.closest('[data-transit]');
  if (!form) return;
  event.preventDefault();
  if (saving || !['planning', 'proformas'].includes(mode)) return;
  const hours = Number(form.querySelector('input').value);
  if (!Number.isFinite(hours) || hours < 0) return;
  const next = clone(working), raw = next.find((ship) => ship.id === selected);
  const ship = {...raw, stops: mode === 'proformas' ? clone(proformaDraft.stops) : stopsFor(raw, form.dataset.voyage, true)};
  const index = ship.stops.findIndex((stop) => stop.id === form.dataset.transit), stop = ship.stops[index];
  const transitMinutes = Math.round(hours * 60);
  const delta = instant(ship.stops[index - 1].departure) + transitMinutes * 60000 - instant(stop.arrival);
  stop.transitMinutes = transitMinutes;
  if ($('#cascade').checked) shiftStops(ship, index, delta);
  else {
    stop.arrival = iso(instant(stop.arrival) + delta);
    stop.departure = iso(instant(stop.departure) + delta);
  }
  if (mode === 'proformas') { proformaDraft.stops = ship.stops; proformaDirty = true; render(); }
  else commit(next);
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
  try { localStorage.setItem(storageKey('harborline-view'), name); } catch {}
});
$('#save-view').addEventListener('click', () => {
  const name = $('#view-name').value.trim();
  if (!name) { notify('Bitte einen Namen f\u00fcr die Ansicht eingeben.', true); return; }
  const config = {collapsed: [...collapsed], hiddenBerths: [...hiddenBerths], dayWidth, voyageDate: activeDate,
    start: iso(START), end: iso(END - DAY), selected, compareProforma, harborOverview, selectedPorts: [...selectedPorts], scrollLeft: $('#chart-scroll').scrollLeft, scrollTop: $('#chart-scroll').scrollTop};
  try {
    const updated = {...views, [name]: config};
    localStorage.setItem(storageKey('harborline-views'), JSON.stringify(updated));
    localStorage.setItem(storageKey('harborline-view'), name);
    views = updated;
    populateViews(name);
    $('#view-options').open = false;
    notify('Ansicht in diesem Browser gespeichert.');
  } catch (error) { notify(error.message, true); }
});
$('#reset-view').addEventListener('click', () => {
  collapsed.clear(); hiddenBerths.clear(); $('#view-select').value = '';
  renderChart(); renderBerthOptions();
});

$('#stop-form').addEventListener('submit', (event) => {
  event.preventDefault();
  if (saving || !['planning', 'proformas'].includes(mode)) return;
  const next = clone(working), ship = next.find((item) => item.id === editing.shipId);
  const editableShip = {...ship, stops: mode === 'proformas' ? clone(proformaDraft.stops) : stopsFor(ship, editing.date, true)};
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
  if (mode === 'proformas') { proformaDraft.stops = editableShip.stops; proformaDirty = true; render(); }
  else commit(next);
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
  if (harborOverview) {
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
    const nextShip = {...raw, stops: mode === 'proformas' ? clone(proformaDraft.stops) : stopsFor(raw, voyageDate, true)}, nextStop = nextShip.stops[index];
    selected = shipId;
    activeDate = voyageDate;
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
    if (mode === 'proformas') { proformaDraft.stops = nextShip.stops; proformaDirty = true; }
    else commit(next);
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
  if (event.target.value === '__ports__') {
    harborOverview = true;
    mode = 'planning';
    if (!selectedPorts.size) selectedPorts = new Set(shipById(selected).stops.map((stop) => stop.portId));
    $('#inspector').hidden = true;
    render();
    return;
  }
  harborOverview = false;
  selectedService = event.target.value;
  selectShip(working.find((ship) => ship.serviceId === selectedService).id, true);
});
$('#fleet').addEventListener('click', (event) => {
  if (event.target.closest('[data-template]')) { proformaTemplate = true; render(); focusShip(); return; }
  const button = event.target.closest('[data-select]');
  if (button) selectShip(button.dataset.select, true);
});
$('#fleet').addEventListener('change', (event) => {
  const id = event.target.dataset.pickPort;
  if (!id) return;
  if (event.target.checked) selectedPorts.add(id); else selectedPorts.delete(id);
  render();
});
$('#route').addEventListener('click', (event) => { const button = event.target.closest('[data-detail]'); if (button) openInspector(selected, button.dataset.detail); });
$('#focus').addEventListener('click', focusShip);
$('#today').addEventListener('click', jumpToToday);
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
    const response = await fetch(`/api/ships/${shipId}/plan`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({dataSignature: saved.dataSignature, ship: before.find((ship) => ship.id === shipId)})});
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
  if (mode === 'fleet' || mode === 'ports') return;
  if ($('#add-port-dialog').open) return;
  if (event.key === 'Escape') $('#inspector').hidden = true;
  if (event.target.matches('input,select,textarea')) return;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); $(event.shiftKey ? '#redo' : '#undo').click(); }
});

async function initialize() {
  try {
    const response = await fetch('/api/plan');
    const plan = await response.json();
    if (!response.ok) throw new Error(plan.error || 'Fahrpl\u00e4ne konnten nicht geladen werden.');
    saved = plan;
    working = clone(saved.ships);
    if (!working.length) throw new Error('Keine Schiffsdateien vorhanden.');
    const firstShip = working[0];
    const firstAssignment = [...assignmentsFor(firstShip)].sort((left, right) => left.validFrom.localeCompare(right.validFrom))[0];
    const firstVersion = firstAssignment ? serviceProforma(firstShip, firstAssignment.proformaId) : proformasFor(firstShip)[0];
    selected = firstShip.id;
    selectedService = firstShip.serviceId;
    activeProforma = firstVersion?.id || null;
    activeDate = iso(localToday()).slice(0, 10);
    $('#import-vessel').value = firstShip.vesselName || firstShip.name;
    const importToday = new Date();
    const importStart = Date.UTC(importToday.getFullYear(), importToday.getMonth(), importToday.getDate());
    $('#import-from').value = iso(importStart).slice(0, 10);
    $('#import-to').value = iso(addMonths(importStart, 2)).slice(0, 10);
    try {
      const draft = JSON.parse(localStorage.getItem(storageKey('harborline-draft')) || 'null');
      if (draft?.dataSignature && Array.isArray(draft.ships) && draft.ships.every((ship) => Array.isArray(ship.proformaAssignments) && ship.voyages)) {
        if (draft.dataSignature && draft.dataSignature !== saved.dataSignature) {
          const fresh = saved;
          if (Array.isArray(draft.baseShips)) saved = {...saved, dataSignature: draft.dataSignature, ships: draft.baseShips};
          notify('Die JSON-Dateien wurden extern ge\u00e4ndert. Dein Entwurf bleibt erhalten. Vor dem Aktualisieren bitte exportieren oder verwerfen.', true);
          dataChangeNotice = fresh.dataSignature;
        }
        working = draft.ships.map((ship) => ({...saved.ships.find((item) => item.id === ship.id), ...ship, maxSpeedKnots: ship.maxSpeedKnots ?? saved.ships.find((item) => item.id === ship.id)?.maxSpeedKnots}));
        mode = 'planning';
        activeProforma = draft.activeProforma || firstVersion?.id || null;
        if (working.some((ship) => ship.id === draft.selected)) selected = draft.selected;
        if (!working.some((ship) => ship.id === selected)) selected = working[0].id;
        selectedService = working.find((ship) => ship.id === selected).serviceId;
        if (/^\d{4}-\d{2}-\d{2}$/.test(draft.activeDate || '')) activeDate = draft.activeDate;
        if (!dataChangeNotice) notify('Lokaler Entwurf wiederhergestellt.');
      } else if (draft) { notify('Ein \u00e4lterer lokaler Entwurf passt nicht zum aktuellen Plan. Er bleibt im Browser gespeichert.', true); }
    } catch { localStorage.removeItem(storageKey('harborline-draft')); }
    renderServiceOptions();
    updateImportScope();
    let localViews = {};
    try { localViews = JSON.parse(localStorage.getItem(storageKey('harborline-views')) || '{}'); } catch {}
    views = localViews && typeof localViews === 'object' && !Array.isArray(localViews) ? localViews : {};
    let viewName = '';
    try { viewName = localStorage.getItem(storageKey('harborline-view')) || ''; } catch {}
    populateViews(viewName);
    if (views[viewName]) applyView(views[viewName]);
    render();
    icons();
  } catch (error) { $('#chart').innerHTML = `<div class="empty-error">${escapeHtml(error.message)} Bitte die Seite neu laden.</div>`; notify(error.message, true); }
}
initialize();

async function refreshData() {
  if (!saved || saving || refreshingData || activeDrag || !$('#inspector').hidden || $('#add-port-dialog').open) return;
  refreshingData = true;
  try {
    const response = await fetch('/api/plan', {cache: 'no-store'});
    const next = await response.json();
    if (!response.ok) throw new Error(next.error || 'JSON-Daten konnten nicht geladen werden.');
    if (!Array.isArray(next.ships) || !next.ships.length) throw new Error('Keine g\u00fcltigen Schiffsdateien vorhanden.');
    dataLoadNotice = '';
    if (next.dataSignature === saved.dataSignature) return;
    const focused = document.activeElement;
    if (dirtyCount() || (typeof masterDataDirty !== 'undefined' && masterDataDirty) || focused?.matches('input,select,textarea') || $('#view-options').open) {
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
    renderServiceOptions();
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

function importPayload() {
  const text = $('#import-text').value.trim();
  const payload = {scope: $('#import-scope').value, serviceId: $('#import-scope').value === 'service' ? $('#import-service').value : null, excludedShips: [...importExcludedShips], choices: importChoices, vesselName: $('#import-vessel').value.trim(), fromDate: $('#import-from').value, toDate: $('#import-to').value, voyageDate: $('#import-voyage').value || null};
  if (text.startsWith('{')) {
    payload.packet = JSON.parse(text);
    if (['maersk', 'hapag'].includes(payload.packet.source) && payload.packet.source !== $('#import-source').value) throw new Error('Die Importdaten passen nicht zur ausgewaehlten Datenquelle.');
  } else {
    if ($('#import-source').value === 'hapag') throw new Error('Fuer Hapag-Lloyd bitte live abrufen oder eine normalisierte Hapag-Import-JSON laden.');
    payload.text = text;
  }
  return payload;
}

function updateImportApply() {
  const involved = importPreview?.candidates?.map((ship) => ship.id) || [importPreview?.shipId];
  const pending = importPreview && working.some((ship) => involved.includes(ship.id) && shipDirtyCount(ship));
  const removed = importPreview?.changes.some((change) => change.status === 'removed');
  $('#import-calendar-pending').hidden = !pending;
  $('#import-calendar-pending').textContent = importPreview?.scope === 'service' ? 'F\u00fcr mindestens ein eingeschlossenes Schiff liegt ein offener Kalenderentwurf vor.' : 'F\u00fcr dieses Schiff liegt bereits ein offener Kalenderentwurf vor.';
  let unchanged = false;
  try { unchanged = importFingerprint === JSON.stringify(importPayload()); } catch {}
  const reasons = [];
  if (importing) reasons.push('Import wird verarbeitet.');
  if (!importPreview?.candidate) reasons.push('Zuerst eine g\u00fcltige Importvorschau berechnen.');
  else {
    if (!unchanged) reasons.push('Eingaben wurden ge\u00e4ndert: Vorschau neu berechnen.');
    if (importPreview.unresolved.length) reasons.push(`${importPreview.unresolved.length} eingeschlossene Aufenthalte sind nicht zugeordnet. Hafen oder \u201eIgnorieren\u201c ausw\u00e4hlen.`);
    if (importPreview.errors?.length) reasons.push(`${importPreview.errors.length} Schiffsergebnisse sind fehlgeschlagen oder unvollst\u00e4ndig. Erneut abrufen oder das Schiff ausdr\u00fccklich ausschlie\u00dfen.`);
    if (pending) reasons.push('F\u00fcr mindestens ein eingeschlossenes Schiff besteht ein offener Kalenderentwurf.');
    if (!$('#import-confirm-time').checked) reasons.push('Zeitbasis der importierten Uhrzeiten best\u00e4tigen.');
    if (removed && !$('#import-confirm-removals').checked) reasons.push('Das Entfernen bisheriger Aufenthalte best\u00e4tigen.');
  }
  $('#import-apply').disabled = reasons.length > 0;
  $('#import-apply').textContent = importPreview?.scope === 'service' ? `Import f\u00fcr Dienst ${importPreview.serviceId} \u00fcbernehmen` : 'Import f\u00fcr dieses Schiff \u00fcbernehmen';
  let blockers = $('#import-blockers');
  if (!blockers) { blockers = document.createElement('ul'); blockers.id = 'import-blockers'; blockers.className = 'import-blockers'; blockers.setAttribute('aria-live', 'polite'); $('#import-apply').before(blockers); }
  blockers.replaceChildren(...reasons.map((reason) => { const item = document.createElement('li'); item.textContent = reason; return item; }));
  blockers.hidden = !reasons.length;
}

function renderImportPreview() {
  $('#import-review').hidden = !importPreview;
  if (!importPreview) { $('#import-state').textContent = 'Keine Vorschau'; updateImportApply(); return; }
  const preview = importPreview;
  $('#import-service-results').hidden = preview.scope !== 'service';
  $('#import-ships').innerHTML = (preview.shipPreviews || []).map((ship) => `<tr class="${ship.error ? 'unmapped-row' : ''}"><td><input type="checkbox" data-import-ship="${escapeHtml(ship.shipId)}" aria-label="${escapeHtml(ship.vesselName)} einschlie\u00dfen" ${ship.excluded ? '' : 'checked'}></td><td><strong>${escapeHtml(ship.vesselName)}</strong></td><td>${escapeHtml(ship.voyageDate || '-')}</td><td>${escapeHtml(ship.excluded ? 'Ausgeschlossen' : ship.error || `${ship.changes} \u00c4nderungen`)}</td></tr>`).join('');
  $('#import-state').textContent = 'PENDING';
  $('#import-summary').textContent = `${preview.rows.length} Aufenthalte / ${preview.rows.filter((row) => !row.include).length} ignoriert / ${preview.unresolved.length} ungekl\u00e4rt`;
  if (preview.preservedCount) $('#import-summary').textContent += ` / ${preview.preservedCount} bestehende Aufenthalte gesch\u00fctzt`;
  $('#import-voyage-info').textContent = preview.scope === 'service' ? `Dienst ${preview.serviceId} / ${preview.candidates.length} eingeschlossene Schiffe` : `${preview.vesselName} / Reise ${preview.voyageDate || '-'}`;
  $('#import-mappings').innerHTML = preview.rows.map((row) => `<tr class="${!row.include ? 'ignored-row' : !row.portId ? 'unmapped-row' : ''}"><td><input type="checkbox" data-import-include="${escapeHtml(row.id)}" aria-label="${escapeHtml(row.portName)} einschlie\u00dfen" ${row.include ? 'checked' : ''}>${!row.include ? '<span class="ignored-tag">Ignoriert</span>' : ''}</td><td>${row.vesselName ? `<small>${escapeHtml(row.vesselName)}</small>` : ''}<strong>${escapeHtml(row.portName)}</strong><small>${escapeHtml(row.terminalName || '')}</small></td><td>${shortDate(instant(row.arrival))}</td><td>${shortDate(instant(row.departure))}</td><td><select data-import-port="${escapeHtml(row.id)}" aria-label="Hafenzuordnung ${escapeHtml(row.portName)}"><option value="__ignore__" ${!row.include ? 'selected' : ''}>Ignorieren</option><option value="" ${row.include && !row.portId ? 'selected' : ''}>Nicht zugeordnet</option>${saved.ports.map((port) => `<option value="${escapeHtml(port.id)}" ${row.include && port.id === row.portId ? 'selected' : ''}>${escapeHtml(port.name)}</option>`).join('')}</select></td></tr>`).join('');
  const names = {new: 'Neu', changed: 'Ge\u00e4ndert', removed: 'Entfernt', unchanged: 'Unver\u00e4ndert'};
  for (const option of $('#import-mappings').querySelectorAll('select option')) {
    const port = saved.ports.find((item) => item.id === option.value);
    if (port) option.textContent = portLabel(port);
  }
  [...$('#import-mappings').rows].forEach((element, index) => {
    if (!preview.rows[index].outsideWindow) return;
    element.title = 'Au\u00dferhalb des Importzeitraums: wird nicht ge\u00e4ndert';
    element.querySelectorAll('input,select').forEach((input) => { input.disabled = true; });
    const tag = element.querySelector('.ignored-tag');
    if (tag) tag.textContent = 'Gesch\u00fctzt';
  });
  const stamp = (value) => value ? shortDate(instant(value)) : '-';
  $('#import-differences').innerHTML = preview.changes.map((change) => `<tr class="diff-${change.status}"><td><span class="diff-tag">${names[change.status]}</span></td><td>${change.vesselName ? `<small>${escapeHtml(change.vesselName)}</small>` : ''}${escapeHtml(saved.ports.find((port) => port.id === change.portId)?.name || change.portId)}</td><td>${stamp(change.before?.arrival)}</td><td>${stamp(change.after?.arrival)}</td><td>${stamp(change.before?.departure)}</td><td>${stamp(change.after?.departure)}</td><td>${change.before?.berth || '-'} &rarr; ${change.after?.berth || '-'}</td></tr>`).join('');
  $('#import-removals-label').hidden = !preview.changes.some((change) => change.status === 'removed');
  updateImportApply();
}

async function calculateImportPreview() {
  if (importing) { if (calculatingImport) importPreviewQueued = true; return; }
  calculatingImport = true;
  importing = true;
  $('#import-preview').disabled = true;
  $('#import-error').textContent = '';
  try {
    const payload = importPayload(), fingerprint = JSON.stringify(payload);
    $('#import-confirm-time').checked = false; $('#import-confirm-removals').checked = false;
    const response = await fetch('/api/import/preview', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: fingerprint});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Importvorschau fehlgeschlagen.');
    if (fingerprint !== JSON.stringify(importPayload())) { importPreviewQueued = true; return; }
    importPreview = result;
    importFingerprint = fingerprint;
    renderImportPreview();
  } catch (error) { importPreview = null; renderImportPreview(); $('#import-error').textContent = error.message; }
  finally {
    calculatingImport = false; importing = false;
    $('#import-preview').disabled = false; updateImportApply();
    if (importPreviewQueued) { importPreviewQueued = false; await calculateImportPreview(); }
  }
}

$('#import-form').addEventListener('submit', (event) => { event.preventDefault(); calculateImportPreview(); });
function updateImportScope() {
  const serviceMode = $('#import-scope').value === 'service';
  $('#import-vessel-field').hidden = serviceMode;
  $('#import-service-field').hidden = !serviceMode;
  $('#import-vessel').required = !serviceMode;
  const label = $('#import-source').selectedOptions[0].textContent;
  $('#import-live').textContent = serviceMode ? `${label}: Dienst live abrufen` : `${label} live abrufen`;
}
for (const selector of ['#import-scope', '#import-service', '#import-source']) $(selector).addEventListener('change', () => {
  importPreview = null; importChoices = {}; importExcludedShips.clear();
  updateImportScope(); renderImportPreview();
});
$('#import-ships').addEventListener('change', (event) => {
  const id = event.target.dataset.importShip;
  if (!id) return;
  if (event.target.checked) importExcludedShips.delete(id); else importExcludedShips.add(id);
  calculateImportPreview();
});
$('#import-live').addEventListener('click', async () => {
  if (importing) return;
  importing = true;
  importPreview = null;
  renderImportPreview();
  $('#import-error').textContent = '';
  $('#import-state').textContent = 'Live-Abruf l\u00e4uft';
  const controls = [...$('#import-form').querySelectorAll('input,select,textarea,button')];
  const disabled = controls.map((control) => control.disabled);
  controls.forEach((control) => { control.disabled = true; });
  let loaded = false;
  try {
    const source = $('#import-source').value;
    const label = $('#import-source').selectedOptions[0].textContent;
    const serviceMode = $('#import-scope').value === 'service';
    const members = serviceMode ? saved.ships.filter((ship) => ship.serviceId === $('#import-service').value) : [{vesselName: $('#import-vessel').value}];
    if (!members.length) throw new Error('Der Dienst enth\u00e4lt keine Schiffe.');
    const packets = [], errors = [];
    for (const [index, ship] of members.entries()) {
      const name = (ship.vesselName || ship.name).trim();
      $('#import-state').textContent = `Live-Abruf ${index + 1}/${members.length}: ${name}`;
      try {
        const response = await fetch(`/api/import/${encodeURIComponent(source)}/live`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({vesselName: name, fromDate: $('#import-from').value, toDate: $('#import-to').value})});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Live-Abruf fehlgeschlagen.');
        packets.push(result.packet);
      } catch (error) {
        if (!serviceMode) throw error;
        errors.push({shipId: ship.id, vesselName: name, error: error.message});
      }
    }
    const packet = serviceMode ? {schemaVersion: 1, source, serviceId: $('#import-service').value, packets, errors} : packets[0];
    $('#import-text').value = JSON.stringify(packet, null, 2);
    $('#import-origin').textContent = serviceMode ? `Live: ${label} / ${packets.length} erfolgreich / ${errors.length} fehlgeschlagen` : `Live: ${label} / ${packet.fetchedAt}`;
    importChoices = {};
    importExcludedShips.clear();
    loaded = true;
  } catch (error) { $('#import-error').textContent = error.message; $('#import-state').textContent = 'Live-Abruf fehlgeschlagen'; }
  finally {
    importing = false;
    controls.forEach((control, index) => { control.disabled = disabled[index]; });
    updateImportApply();
  }
  if (loaded) await calculateImportPreview();
});
$('#import-file').addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) { $('#import-error').textContent = 'Datei ist gr\u00f6\u00dfer als 2 MB.'; return; }
  $('#import-text').value = await file.text();
  try {
    const packet = JSON.parse($('#import-text').value);
    if (['maersk', 'hapag'].includes(packet.source)) $('#import-source').value = packet.source;
    if (packet.packets && packet.serviceId) { $('#import-scope').value = 'service'; $('#import-service').value = packet.serviceId; }
    else { $('#import-scope').value = 'ship'; if (packet.vesselName) $('#import-vessel').value = packet.vesselName; }
    if (packet.fromDate) $('#import-from').value = packet.fromDate;
    if (packet.toDate) $('#import-to').value = packet.toDate;
    updateImportScope();
  } catch {}
  $('#import-origin').textContent = file.name;
  importChoices = {}; importPreview = null; importExcludedShips.clear();
  renderImportPreview();
});
$('#import-mappings').addEventListener('change', (event) => {
  const input = event.target, id = input.dataset.importInclude || input.dataset.importPort;
  if (!id || !importPreview) return;
  const row = importPreview.rows.find((item) => item.id === id);
  importChoices[id] = {...(importChoices[id] || {}), include: row.include, portId: row.portId};
  if (input.dataset.importInclude) importChoices[id].include = input.checked;
  else {
    importChoices[id].include = input.value !== '__ignore__';
    importChoices[id].portId = input.value && input.value !== '__ignore__' ? input.value : null;
  }
  calculateImportPreview();
});
for (const selector of ['#import-confirm-time', '#import-confirm-removals']) $(selector).addEventListener('change', updateImportApply);
$('#import-clear').addEventListener('click', () => {
  importPreview = null; importChoices = {}; importExcludedShips.clear();
  $('#import-error').textContent = ''; $('#import-confirm-time').checked = false; $('#import-confirm-removals').checked = false;
  renderImportPreview();
});
$('#import-text').addEventListener('input', () => { importPreview = null; importChoices = {}; importExcludedShips.clear(); renderImportPreview(); });
for (const selector of ['#import-vessel', '#import-from', '#import-to', '#import-voyage']) $(selector).addEventListener('input', () => { importPreview = null; renderImportPreview(); });
$('#import-apply').addEventListener('click', async () => {
  if (importing || !importPreview || $('#import-apply').disabled) return;
  importing = true; updateImportApply();
  $('#import-error').textContent = '';
  try {
    const response = await fetch('/api/import/apply', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...importPayload(), dataSignature: importPreview.dataSignature, confirmTimeBasis: $('#import-confirm-time').checked, confirmRemovals: $('#import-confirm-removals').checked})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Import konnte nicht \u00fcbernommen werden.');
    const pending = new Map(working.filter((ship) => shipDirtyCount(ship)).map((ship) => [ship.id, ship]));
    const serviceMode = importPreview.scope === 'service';
    saved = result;
    working = saved.ships.map((ship) => clone(pending.get(ship.id) || ship));
    history = []; future = []; persistDraft();
    importPreview = null; renderImportPreview();
    $('#import-state').textContent = '\u00dcbernommen';
    notify(serviceMode ? 'Dienstimport \u00fcbernommen. Proformas unver\u00e4ndert.' : 'Import f\u00fcr dieses Schiff \u00fcbernommen. Proforma unver\u00e4ndert.');
    if (result.importWarnings?.length) alert(`Import wurde durchgefuehrt. Dabei sind Konflikte entstanden:\n\n${result.importWarnings.map((warning) => `• ${warning}`).join('\n')}`);
  } catch (error) { $('#import-error').textContent = error.message; }
  finally { importing = false; updateImportApply(); }
});
for (const [selector, field, convert] of [['#proforma-name', 'name', (value) => value], ['#proforma-start', 'validFrom', (value) => value], ['#proforma-weeks', 'repeatWeeks', Number]]) {
  $(selector).addEventListener('input', (event) => {
    if (!proformaDraft) return;
    proformaDraft[field] = convert(event.target.value);
    proformaDirty = true;
    $('#proforma-save').disabled = false;
    $('#proforma-cancel').disabled = false;
    $('#status').textContent = 'Proforma-Entwurf';
  });
}
$('#proforma-new').addEventListener('click', () => {
  const ship = working.find((item) => item.id === selected), source = serviceProforma(ship, activeProforma) || proformaDraft;
  if (!source?.stops?.length) { notify('Zum Erstellen einer Proforma wird zuerst eine Hafenfolge benoetigt.', true); return; }
  const year = Number(source.validFrom.slice(0, 4)) + 1, serviceId = ship.serviceId;
  let id = `${serviceId.toLowerCase()}-${year}`, suffix = 2;
  while (proformasFor(ship).some((item) => item.id === id)) { id = `${serviceId.toLowerCase()}-${year}-${suffix}`; suffix++; }
  const delta = Date.UTC(year, 0, 1) - Date.UTC(Number(source.validFrom.slice(0, 4)), 0, 1);
  proformaDraft = {...clone(source), id, name: `${serviceId}/${year}`, validFrom: `${year}-01-01`, stops: source.stops.map((stop) => ({...stop, arrival: iso(instant(stop.arrival) + delta), departure: iso(instant(stop.departure) + delta)}))};
  activeProforma = id; proformaIsNew = true; proformaDirty = true;
  activeDate = proformaDraft.stops[0].arrival.slice(0, 10);
  render(); focusShip();
});
$('#proforma-cancel').addEventListener('click', () => {
  if (!proformaDraft || !confirm('Proforma-Entwurf verwerfen?')) return;
  if (proformaIsNew) activeProforma = assignmentsFor(working.find((item) => item.id === selected))[0]?.proformaId || proformasFor(working.find((item) => item.id === selected))[0]?.id || null;
  proformaDraft = clone(serviceProforma(working.find((item) => item.id === selected), activeProforma));
  proformaDirty = false; proformaIsNew = false; render();
});
$('#proforma-save').addEventListener('click', async () => {
  if (!proformaDraft || !proformaDirty || saving) return;
  const candidate = {...clone(proformaDraft), name: $('#proforma-name').value.trim(), validFrom: $('#proforma-start').value, repeatWeeks: Number($('#proforma-weeks').value)};
  if (!candidate.name || !candidate.validFrom || !Number.isInteger(candidate.repeatWeeks) || candidate.repeatWeeks < 1 || candidate.repeatWeeks > 104) { notify('Name, Geltungsbeginn und Zyklus pruefen.', true); return; }
  saving = true; $('#proforma-save').disabled = true;
  try {
    const ship = working.find((item) => item.id === selected), method = proformaIsNew ? 'POST' : 'PUT';
    const path = `/api/services/${encodeURIComponent(ship.serviceId)}/proformas${proformaIsNew ? '' : `/${encodeURIComponent(candidate.id)}`}`;
    const response = await fetch(path, {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify({dataSignature: saved.dataSignature, proforma: candidate})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Proforma konnte nicht gespeichert werden.');
    saved = result; working = clone(saved.ships); proformaDraft = clone(serviceProforma(working.find((item) => item.id === selected), candidate.id));
    proformaDirty = false; proformaIsNew = false; history = []; future = []; render();
    notify('Dienst-Proforma gespeichert.');
  } catch (error) { notify(error.message, true); }
  finally { saving = false; renderProformaControls(); }
});
$('#proforma-service').addEventListener('change', (event) => {
  if (proformaDirty && !confirm('Ungespeicherte Proforma-Aenderungen verwerfen?')) { event.target.value = selectedService; return; }
  const ship = working.find((item) => item.serviceId === event.target.value);
  if (!ship) { notify('Dieser Dienst hat keine Schiffe.', true); event.target.value = selectedService; return; }
  selected = ship.id; selectedService = ship.serviceId;
  activeProforma = assignmentsFor(ship)[0]?.proformaId || proformasFor(ship)[0]?.id || null;
  proformaDraft = clone(serviceProforma(ship, activeProforma));
  proformaDirty = false; proformaIsNew = false; render(); focusShip();
});