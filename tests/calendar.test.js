const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
function setup() {
  const context = vm.createContext({structuredClone, document: {querySelector: () => ({})}});
  vm.runInContext(source.slice(0, source.indexOf('function stopsFor(')), context);
  vm.runInContext(source.slice(source.indexOf('function stopsFor('), source.indexOf('function displayVoyage(')), context);
  vm.runInContext(source.slice(source.indexOf('function visibleVoyages('), source.indexOf('function transitRow(')), context);
  vm.runInContext(source.slice(source.indexOf('function selectShip('), source.indexOf('function focusShip(')), context);
  vm.runInContext(`
    saved = {services: []};
    working = [{
      id: 'actual-only', serviceId: 'custom', proformaAssignments: [],
      voyages: {
        '2026-11-21': {proformaId: null, stops: [
          {id: 'first', portId: 'a', arrival: '2026-11-21T11:00', departure: '2026-11-23T00:01'},
          {id: 'last', portId: 'b', arrival: '2026-12-01T12:00', departure: '2026-12-03T23:00'}
        ]}
      }
    }];
    START = dayInstant('2026-10-01');
    END = dayInstant('2027-01-01');
    activeDate = '2026-10-26';
    function render() {}
    function focusShip() {}
  `, context);
  return (script) => vm.runInContext(script, context);
}

test('actual-only voyage resolves throughout its date span, including transit gaps', () => {
  const run = setup();
  for (const date of ['2026-11-21', '2026-11-22', '2026-11-28', '2026-12-03']) {
    assert.equal(run(`resolveVoyage(working[0], '${date}').key`), '2026-11-21');
  }
  for (const date of ['2026-11-20', '2026-12-04']) {
    assert.equal(run(`resolveVoyage(working[0], '${date}')`), null);
  }
});

test('selecting an actual-only ship chooses its visible saved voyage', () => {
  const run = setup();
  run(`selectShip('actual-only')`);
  assert.equal(run('activeDate'), '2026-11-21');
  assert.equal(run('resolveVoyage(working[0], activeDate).stops.length'), 2);
  assert.equal(run('visibleVoyages(working[0]).length'), 1);
});

test('selecting a ship preserves an already matching date and does not create voyages', () => {
  const run = setup();
  run(`activeDate = '2026-11-28'; selectShip('actual-only')`);
  assert.equal(run('activeDate'), '2026-11-28');
  assert.equal(run('Object.keys(working[0].voyages).length'), 1);
});

test('ships without saved voyages remain unscheduled', () => {
  const run = setup();
  run(`working[0].voyages = {}; selectShip('actual-only')`);
  assert.equal(run('activeDate'), '2026-10-26');
  assert.equal(run('resolveVoyage(working[0], activeDate)'), null);
});

test('proforma template and ship view use separate offsets and require an assignment', () => {
  const run = setup();
  run(`
    saved.services = [{id: 'custom', proformas: [{
      id: 'route', stops: [{id: 'stop', arrival: '2026-11-01T10:00', departure: '2026-11-02T10:00'}]
    }]}];
    mode = 'proformas'; selected = 'actual-only'; activeProforma = 'route';
    working[0].proformaAssignments = [{proformaId: 'route', validFrom: '2026-01-01', offsetWeeks: 3}];
  `);
  assert.equal(run('stopsFor(working[0])[0].arrival'), '2026-11-01T10:00');
  run('proformaTemplate = false');
  assert.equal(run('stopsFor(working[0])[0].arrival'), '2026-11-22T10:00');
  assert.equal(run('saved.services[0].proformas[0].stops[0].arrival'), '2026-11-01T10:00');
  run('working[0].proformaAssignments = []');
  assert.equal(run('visibleVoyages(working[0]).length'), 0);
});

test('today jump scrolls only inside the inclusive displayed date range', () => {
  const run = setup();
  run(`
    const calls = [];
    const notices = [];
    document.querySelector = () => ({scrollTo: value => calls.push(value)});
    function notify(message) { notices.push(message); }
    START = localToday(); END = START + DAY;
    jumpToToday();
  `);
  assert.equal(run('calls.length'), 1);
  assert.equal(run('calls[0].left'), 0);
  run('END = START; START -= DAY; jumpToToday()');
  assert.equal(run('calls.length'), 1);
  assert.equal(run('notices.length'), 1);
});

test('default window starts ten days before today and ends six calendar months after today', () => {
  const context = vm.createContext({structuredClone, document: {querySelector: () => ({})}});
  vm.runInContext(source.slice(0, source.indexOf('function stopsFor(')), context);
  assert.equal(vm.runInContext('START === localToday() - 10 * DAY', context), true);
  assert.equal(vm.runInContext('END === addMonths(localToday(), 6) + DAY', context), true);
});

test('hour displays round minute fractions to two decimals without losing minute precision on save', () => {
  const run = setup();
  assert.equal(run('roundedHours(1799 / 60)'), 29.98);
  assert.equal(run('roundedHours(37 + 1 / 60)'), 37.02);
  for (let minutes = 0; minutes < 10000; minutes++) {
    assert.equal(run(`Math.round(roundedHours(${minutes} / 60) * 60)`), minutes);
  }
});
