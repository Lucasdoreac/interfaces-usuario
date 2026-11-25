import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, useLocation } from 'react-router';
import { FormProvider, useFormContext } from '../src/context/FormContext.jsx';
import EventSchedule from '../src/pages/event-schedule/EventSchedule.jsx';
import EventConfirmData from '../src/pages/event-confirm-data/EventConfirmData.jsx';
import MyEvents from '../src/pages/meus-eventos/MyEvents.jsx';
import apiService from '../src/services/client.js';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
// Fail closed: no network calls from the application.
globalThis.fetch = () => { throw new Error('Unexpected network'); };
apiService.getTypes = async () => ({ types: [] });
let resolveSlow;
let slowNext = false;
let calls = [];
apiService.getAvailableSlots = (startAt, page) => {
  calls.push({startAt, page});
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
  check(new Intl.DateTimeFormat('en-GB', { timeZone: 'America/Sao_Paulo', hour: '2-digit', hourCycle: 'h23' }).format(new Date(context.formData.reservationDate)) === '14', 'hora do turno incorreta');
  const before = context.formData.reservationDate;
  await changeDate();
  check(!button(), 'Continuar permanece após troca de data');
  check(!context.formData.roomId && !context.formData.reservationDate, 'seleção antiga permaneceu no contexto após data');
  await selectRoom();
  check(context.formData.reservationDate !== before, 'data não mudou');
  check(new Intl.DateTimeFormat('en-GB', { timeZone: 'America/Sao_Paulo', hour: '2-digit', hourCycle: 'h23' }).format(new Date(context.formData.reservationDate)) === '14', 'troca de data perdeu horário do turno');
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
  check(new Intl.DateTimeFormat('en-GB', { timeZone: 'America/Sao_Paulo', hour: '2-digit', hourCycle: 'h23' }).format(new Date(context.formData.reservationDate)) === '19', 'hora da seleção final incorreta');
  const saved = JSON.parse(localStorage.getItem('formData'));
  check(saved.reservationDate === calls.at(-1).startAt, 'consulta e persistência divergem');
  check(saved.reservationTimeZone === 'America/Sao_Paulo', 'marcador de fuso ausente');
  await act(async () => { root2.unmount(); });
  let submitted = null;
  apiService.submitEventForApproval = async (id, data) => { submitted = {id, data}; throw Object.assign(new Error('conflict'), {status: 409}); };
  const root3 = createRoot(document.getElementById('root'));
  await act(async () => { root3.render(<MemoryRouter initialEntries={['/event/confirm-data?eventId=test-event']}><FormProvider><EventConfirmData /></FormProvider></MemoryRouter>); });
  check(document.body.textContent.includes('horário de Brasília'), 'resumo não indica Brasília');
  await click([...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Confirmar'));
  check(submitted?.data.reservationDate === saved.reservationDate, 'envio alterou instante');
  check(document.body.textContent.includes('Essa sala não está mais disponível'), '409 não exibido');
  await act(async () => { root3.unmount(); });
  localStorage.setItem('formData', JSON.stringify({roomId:'old', reservationDate:'2026-11-25T22:00:00Z'}));
  submitted = null;
  const root4 = createRoot(document.getElementById('root'));
  await act(async () => { root4.render(<MemoryRouter initialEntries={['/event/confirm-data?eventId=test-event']}><FormProvider><EventConfirmData /></FormProvider></MemoryRouter>); });
  await click([...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Confirmar'));
  check(!submitted && document.body.textContent.includes('Selecione novamente'), 'rascunho antigo ambíguo aceito');
  await act(async () => { root4.unmount(); });
  localStorage.setItem('userEmail', 'synthetic@example.test');
  apiService.getUserEvents = async () => ({events:[{_id:'test-event', name:'Sintético'}]});
  apiService.getEventsReservations = async () => ({startAt:'2026-11-26T02:30:00Z', endAt:'2026-11-26T05:30:00Z'});
  const root5 = createRoot(document.getElementById('root'));
  await act(async () => { root5.render(<MemoryRouter><FormProvider><MyEvents /></FormProvider></MemoryRouter>); });
  check(document.body.textContent.includes('25/11/2026') && document.body.textContent.includes('23:30 - 02:30 (26/11/2026)'), 'Meus Eventos: dia ou horas incorretos');
  await act(async () => { root5.unmount(); });
  document.getElementById('result').textContent = 'PASS';
} catch (error) { document.getElementById('result').textContent = `FAIL: ${error.stack || error}`; } })();
