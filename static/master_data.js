let masterDataDirty = false, masterKind = null, masterRecordId;

function renderShipAssignments(record) {
  const container = $('#ship-proforma-assignments');
  const serviceId = $('#master-service').value;
  const versions = saved.services.find((service) => service.id === serviceId)?.proformas || [];
  const assignments = record?.proformaAssignments || [];
  container.innerHTML = assignments.map((assignment) => `<div class="assignment-row"><label>Proforma<select data-assignment-proforma required><option value="">Ausw&auml;hlen</option>${versions.map((version) => `<option value="${escapeHtml(version.id)}" ${version.id === assignment.proformaId ? 'selected' : ''}>${escapeHtml(version.name)} / ${version.validFrom}</option>`).join('')}</select></label><label>G&uuml;ltig ab<input type="date" data-assignment-from value="${escapeHtml(assignment.validFrom)}" required></label><label>Versatz (Wochen)<input type="number" min="-104" max="104" step="1" data-assignment-offset value="${assignment.offsetWeeks}" required></label><button type="button" class="button icon" data-assignment-remove title="Zuordnung entfernen" aria-label="Zuordnung entfernen">&times;</button></div>`).join('');
}

function readShipAssignments() {
  return [...$('#ship-proforma-assignments').querySelectorAll('.assignment-row')].map((row) => ({
    proformaId: row.querySelector('[data-assignment-proforma]').value,
    validFrom: row.querySelector('[data-assignment-from]').value,
    offsetWeeks: Number(row.querySelector('[data-assignment-offset]').value),
  })).filter((item) => item.proformaId || item.validFrom);
}

function renderPluginLocations(record, fleet) {
  $('#master-port-plugins').open = false;
  if (globalThis.PortPlugins) PortPlugins.mountSettings($('#master-plugin-locations'), fleet ? null : record || {});
}

document.addEventListener('phoca-plugins-ready', () => {
  if (mode === 'ports' && !masterDataDirty) renderPluginLocations(saved.ports.find(port => port.id === masterRecordId), false);
});
function renderMasterPanel(kind) {
  if (masterKind !== kind) { masterKind = kind; masterRecordId = undefined; }
  const fleet = kind === 'fleet', records = fleet ? saved.ships : saved.ports;
  if (masterRecordId === undefined) masterRecordId = records[0]?.id || null;
  const record = records.find((item) => item.id === masterRecordId);
  $('#master-title').textContent = fleet ? 'Flotte' : 'H\u00e4fen';
  $('#master-new').textContent = fleet ? 'Schiff anlegen' : 'Hafen anlegen';
  $('#master-list').innerHTML = records.map((item) => `<button type="button" class="master-record ${item.id === masterRecordId ? 'active' : ''}" data-master-id="${escapeHtml(item.id)}"><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(fleet ? item.serviceId : `${item.id} / ${item.berths} Liegepl\u00e4tze`)}</small></button>`).join('');
  for (const field of document.querySelectorAll('[data-master-kind]')) field.hidden = field.dataset.masterKind !== kind;
  $('#master-id').value = record?.id || '';
  $('#master-id').readOnly = fleet && !!record;
  $('#master-id').required = !fleet && !!record;
  $('#master-name').value = record?.name || '';
  $('#master-name').maxLength = fleet ? 120 : 160;
  $('#master-vessel').value = record?.vesselName || (fleet ? record?.name || '' : '');
  $('#master-service').value = fleet ? record?.serviceId || saved.services[0]?.id || '' : '';
  $('#master-services').innerHTML = saved.services.map((service) => `<option value="${escapeHtml(service.id)}"></option>`).join('');
  $('#master-speed').value = record?.maxSpeedKnots ?? '';
  $('#master-vessel').required = $('#master-service').required = $('#master-speed').required = fleet;
  $('#master-berths').required = !fleet;
  $('#master-berths').value = record?.berths ?? '';
  $('#master-aliases').value = JSON.stringify(record?.aliases || {}, null, 2);
  renderPluginLocations(record, fleet);
  $('#master-distances').innerHTML = fleet ? '' : saved.ports.filter((port) => port.id !== record?.id).map((port) => `<label>${escapeHtml(port.name)} <small>${escapeHtml(port.id)}</small><input type="number" min="0" step="0.1" data-distance-port="${escapeHtml(port.id)}" value="${record?.distancesNm?.[port.id] ?? port.distancesNm?.[record?.id] ?? ''}" required></label>`).join('');
  renderShipAssignments(fleet ? record : null);
  $('#master-plan-info').textContent = fleet ? record ? `${record.proformaAssignments.length} Proforma-Zuordnungen / ${Object.keys(record.voyages).length} gespeicherte Reisen` : 'Neues Schiff ohne Fahrplan' : '';
  $('#master-error').textContent = dirtyCount() ? 'Offene Kalenderentw\u00fcrfe zuerst \u00fcbernehmen oder verwerfen.' : '';
  $('#master-save').disabled = !!dirtyCount() || saving;
  masterDataDirty = false;
}

$('#tab-fleet').addEventListener('click', () => switchMode('fleet'));
$('#tab-ports').addEventListener('click', () => switchMode('ports'));
$('#master-form').addEventListener('input', () => { masterDataDirty = true; });
$('#master-form').addEventListener('change', () => { masterDataDirty = true; });
$('#master-form').addEventListener('invalid', (event) => {
  if ($('#master-port-plugins').contains(event.target)) $('#master-port-plugins').open = true;
}, true);
$('#master-new').addEventListener('click', () => {
  if (masterDataDirty && !confirm('Ungespeicherte Stammdaten verwerfen?')) return;
  masterRecordId = null;
  renderMasterPanel(mode);
  $('#master-name').focus();
});
$('#master-reset').addEventListener('click', () => renderMasterPanel(mode));
$('#assignment-add').addEventListener('click', () => {
  const versions = saved.services.find((service) => service.id === $('#master-service').value)?.proformas || [];
  if (!versions.length) { $('#master-error').textContent = 'Fuer diesen Dienst ist noch keine Proforma vorhanden.'; return; }
  $('#ship-proforma-assignments').insertAdjacentHTML('beforeend', `<div class="assignment-row"><label>Proforma<select data-assignment-proforma required><option value="">Ausw&auml;hlen</option>${versions.map((version) => `<option value="${escapeHtml(version.id)}">${escapeHtml(version.name)} / ${version.validFrom}</option>`).join('')}</select></label><label>G&uuml;ltig ab<input type="date" data-assignment-from required></label><label>Versatz (Wochen)<input type="number" min="-104" max="104" step="1" data-assignment-offset value="0" required></label><button type="button" class="button icon" data-assignment-remove title="Zuordnung entfernen" aria-label="Zuordnung entfernen">&times;</button></div>`);
  masterDataDirty = true;
});
$('#ship-proforma-assignments').addEventListener('click', (event) => {
  if (!event.target.closest('[data-assignment-remove]')) return;
  event.target.closest('.assignment-row').remove();
  masterDataDirty = true;
});
$('#master-service').addEventListener('change', () => {
  if (masterRecordId && readShipAssignments().length && !confirm('Dienst geaendert. Die bisherigen Proforma-Zuordnungen entfernen?')) {
    $('#master-service').value = saved.ships.find((ship) => ship.id === masterRecordId)?.serviceId || '';
    return;
  }
  renderShipAssignments(null);
});
$('#master-list').addEventListener('click', (event) => {
  const button = event.target.closest('[data-master-id]');
  if (!button || (masterDataDirty && !confirm('Ungespeicherte Stammdaten verwerfen?'))) return;
  masterRecordId = button.dataset.masterId;
  renderMasterPanel(mode);
});
$('#master-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (saving || dirtyCount()) return;
  const fleet = mode === 'fleet';
  const payload = {dataSignature: saved.dataSignature, id: $('#master-id').value.trim() || null, name: $('#master-name').value.trim()};
  if (!fleet && masterRecordId && payload.id !== masterRecordId && !confirm(`Hafen-ID ${masterRecordId} in ${payload.id} umbenennen? Bestehende Fahrplan- und Dienstverweise werden angepasst.`)) return;
  try {
    if (fleet) Object.assign(payload, {vesselName: $('#master-vessel').value.trim(), serviceId: $('#master-service').value.trim(), maxSpeedKnots: Number($('#master-speed').value), proformaAssignments: readShipAssignments()});
    else {
      const original = saved.ports.find((port) => port.id === masterRecordId);
      const pluginData = PortPlugins.readSettings(original);
      const locations = pluginData.pluginLocations || [];
      Object.assign(payload, {berths: Number($('#master-berths').value), aliases: JSON.parse($('#master-aliases').value),
        distancesNm: Object.fromEntries([...document.querySelectorAll('[data-distance-port]')].map((input) => [input.dataset.distancePort, Number(input.value)])),
        coordinates: original?.coordinates || locations[0]?.coordinates || null, ...pluginData});
    }
    saving = true;
    $('#master-save').disabled = true;
    const path = fleet ? '/api/fleet' : '/api/ports';
    const response = await fetch(masterRecordId ? `${path}/${encodeURIComponent(masterRecordId)}` : path, {method: masterRecordId ? 'PUT' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Stammdaten konnten nicht gespeichert werden.');
    if (result.portIdChange) {
      const {from, to} = result.portIdChange;
      const remap = (id) => id === from ? to : id;
      const remapBerth = (key) => key.startsWith(`${from}:`) ? `${to}${key.slice(from.length)}` : key;
      collapsed = new Set([...collapsed].map(remap));
      selectedPorts = new Set([...selectedPorts].map(remap));
      hiddenBerths = new Set([...hiddenBerths].map(remapBerth));
      for (const config of Object.values(views)) {
        if (Array.isArray(config.collapsed)) config.collapsed = config.collapsed.map(remap);
        if (Array.isArray(config.selectedPorts)) config.selectedPorts = config.selectedPorts.map(remap);
        if (Array.isArray(config.hiddenBerths)) config.hiddenBerths = config.hiddenBerths.map(remapBerth);
      }
      try { localStorage.setItem(storageKey('harborline-views'), JSON.stringify(views)); }
      catch { notify('Hafen-ID ge\u00e4ndert; Browseransichten konnten nicht gespeichert werden.', true); }
      for (const choice of Object.values(importChoices)) if (choice.portId === from) choice.portId = to;
      importPreview = null;
      masterRecordId = to;
    }
    saved = result; working = clone(saved.ships); history = []; future = [];
    if (!working.some((ship) => ship.id === selected)) selected = working[0]?.id;
    if (!masterRecordId) {
      const records = fleet ? saved.ships : saved.ports;
      masterRecordId = records.find((item) => payload.id ? item.id === payload.id : fleet ? item.vesselName?.trim().replace(/\s+/g, ' ').toLocaleLowerCase() === payload.vesselName.trim().replace(/\s+/g, ' ').toLocaleLowerCase() : item.name === payload.name)?.id || null;
    }
    masterDataDirty = false;
    renderServiceOptions();
    renderMasterPanel(mode);
    notify('Stammdaten gespeichert. Vorhandene Fahrpl\u00e4ne bleiben erhalten.');
  } catch (error) { $('#master-error').textContent = error.message; }
  finally { saving = false; $('#master-save').disabled = !!dirtyCount(); }
});