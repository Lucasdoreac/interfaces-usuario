import test from 'node:test';
import assert from 'node:assert/strict';
import { brasiliaCivilToInstant, civilDayToPicker, pickerToCivilDay, todayInBrasilia, formatReservation } from '../src/utils/dateUtils.js';
import { summarizeEventData } from '../src/utils/eventSummary.js';
import { ApiService } from '../src/services/client.js';

test('civil day, instant and displays do not depend on browser timezone', () => {
  for (const zone of ['Asia/Tokyo', 'America/Sao_Paulo', 'UTC', 'America/Los_Angeles']) {
    process.env.TZ = zone;
    assert.equal(todayInBrasilia(new Date('2026-11-26T02:30:00Z')), '2026-11-25');
    assert.equal(pickerToCivilDay(civilDayToPicker('2026-11-25')), '2026-11-25');
    const start = brasiliaCivilToInstant('2026-11-25', '19:00:00').toISOString();
    assert.equal(start, '2026-11-25T22:00:00.000Z');
    assert.equal(brasiliaCivilToInstant('2026-11-25', '23:30:00').toISOString(), '2026-11-26T02:30:00.000Z');
    assert.deepEqual(formatReservation('2026-11-26T02:30:00Z', '2026-11-26T05:30:00Z'), { day: '25/11/2026', hours: '23:30 - 02:30 (26/11/2026)' });
    const saved = JSON.parse(JSON.stringify({reservationDate:start,reservationTimeZone:'America/Sao_Paulo'}));
    assert.equal(summarizeEventData(saved).find(x => x.label === 'Data da reserva').value, '25/11/2026, 19:00 (horário de Brasília)');
    assert.match(summarizeEventData({reservationDate:start})[0].value, /não confirmado/);
    assert.match(formatReservation('2026-11-25T19:00:00', '2026-11-25T22:00:00').day, /Fuso indefinido/);
  }
});
test('IANA historical DST, gaps and repeated times are not guessed', () => {
  assert.equal(brasiliaCivilToInstant('2018-12-01','08:00:00').toISOString(), '2018-12-01T10:00:00.000Z');
  assert.throws(() => brasiliaCivilToInstant('2018-11-04','00:30:00'), /inexistente ou ambíguo/);
  assert.throws(() => brasiliaCivilToInstant('2019-02-16','23:30:00'), /inexistente ou ambíguo/);
  assert.throws(() => brasiliaCivilToInstant('2026-02-30','08:00:00'));
});
test('availability uses only start_at; old API rejects, never falls back', async () => {
  let requests = [];
  const api = new ApiService({baseURL:'https://example.test', storage:null, fetchImpl:async url => {
    requests.push(new URL(url));
    return new Response(JSON.stringify({error:"date and time required"}), {status:400,headers:{'content-type':'application/json'}});
  }});
  await assert.rejects(api.getAvailableSlots('2026-11-25T22:00:00.000Z',1,10,''), e => e.status === 400);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].searchParams.get('start_at'), '2026-11-25T22:00:00.000Z');
  assert.equal(requests[0].searchParams.has('date'), false);
  assert.equal(requests[0].searchParams.has('time'), false);
});
