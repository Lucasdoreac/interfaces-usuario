import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, useLocation } from 'react-router';
import { FormProvider, useFormContext } from '../src/context/FormContext.jsx';
import EventSchedule from '../src/pages/event-schedule/EventSchedule.jsx';
import apiService from '../src/services/client.js';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
// Fail closed: no network calls from the application.
globalThis.fetch = () => { throw new Error('Unexpected network'); };
apiService.getTypes = async () => ({ types: [] });
let resolveSlow;
let slowNext = false;
let calls = [];
apiService.getAvailableSlots = (date, time, page) => {
  calls.push({date, time, page});
  if (slowNext) { slowNext = false; return new Promise(resolve => { resolveSlow = resolve; }); }
  return Promise.resolve({data: [{id: 'room-1', name: 'Sala sintética', campus: 'Teste'}], pagination: {total_pages: 1}});
};
let context, location;
function Probe() { context = useFormContext(); location = useLocation(); return <EventSchedule />; }
function check(value, message) { if (!value) throw new Error(message); }
function button() { return [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Continuar'); }
async function click(el) { check(el, 'missing control'); await act(async () => { el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true})); }); }
async function selectRoom() { await click(document.querySelector('.room-card')); check(button(), 'Continuar ausente após escolher sala'); }
async function changePeriod(value) { await click(document.querySelector(`input[value="${value}"]`)); }
async function changeDate() {
  await click(document.querySelector('.datepicker-component input'));
  let day = document.querySelector('.react-datepicker__day:not(.react-datepicker__day--disabled):not(.react-datepicker__day--selected):not(.react-datepicker__day--outside-month)');
  if (!day) { await click(document.querySelector('.react-datepicker__navigation--next')); day = document.querySelector('.react-datepicker__day:not(.react-datepicker__day--disabled):not(.react-datepicker__day--outside-month)'); }
  await click(day);
}
(async () => { try {
  localStorage.clear(); localStorage.setItem('formData', JSON.stringify({tituloEvento: 'Sintético'}));
  const root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(<MemoryRouter initialEntries={['/event/schedule?eventId=test-event']}><FormProvider><Probe /></FormProvider></MemoryRouter>); });
  await selectRoom();
  check(context.formData.roomId === 'room-1', 'sala inicial não registrada');
  await changePeriod('Tarde');
  check(!button(), 'BUG: Continuar permanece após troca de turno');
  check(!context.formData.roomId && !context.formData.reservationDate, 'seleção antiga permaneceu no contexto após turno');
  await selectRoom();
  check(new Date(context.formData.reservationDate).getHours() === 14, 'hora do turno incorreta');
  const before = context.formData.reservationDate;
  await changeDate();
  check(!button(), 'Continuar permanece após troca de data');
  check(!context.formData.roomId && !context.formData.reservationDate, 'seleção antiga permaneceu no contexto após data');
  await selectRoom();
  check(context.formData.reservationDate !== before, 'data não mudou');
  check(new Date(context.formData.reservationDate).getHours() === 14, 'troca de data perdeu horário do turno');
  check(context.formData.tituloEvento === 'Sintético', 'outros dados foram alterados');
  await click(button());
  check(location.pathname === '/event/confirm-data', 'não navegou após nova escolha');
  await act(async () => { root.unmount(); });
  // A delayed response belonging to an old period cannot bring back its rooms.
  calls = []; slowNext = true; resolveSlow = null;
  const root2 = createRoot(document.getElementById('root'));
  await act(async () => { root2.render(<MemoryRouter initialEntries={['/event/schedule?eventId=test-event']}><FormProvider><Probe /></FormProvider></MemoryRouter>); });
  check(resolveSlow, 'pedido atrasado não iniciado');
  await changePeriod('Noite');
  await act(async () => { resolveSlow({data: [{id: 'old', name: 'Sala antiga', campus: 'Teste'}], pagination: {total_pages: 1}}); });
  check(!document.body.textContent.includes('Sala antiga'), 'resposta antiga sobrescreveu a lista');
  check(document.body.textContent.includes('Sala sintética'), 'lista nova ausente');
  await selectRoom();
  check(new Date(context.formData.reservationDate).getHours() === 19, 'hora da seleção final incorreta');
  await act(async () => { root2.unmount(); });
  document.getElementById('result').textContent = 'PASS';
} catch (error) { document.getElementById('result').textContent = `FAIL: ${error.stack || error}`; } })();
