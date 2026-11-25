export const RESERVATION_ZONE = "America/Sao_Paulo";

const partsFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: RESERVATION_ZONE, year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
});
const parts = (date) => Object.fromEntries(partsFormatter.formatToParts(date).map(({ type, value }) => [type, value]));
const civilDay = (date) => { const p = parts(date); return `${p.year}-${p.month}-${p.day}`; };
export const todayInBrasilia = (now = new Date()) => civilDay(now);

// The picker uses local Date components as a calendar-only carrier, never an instant.
export function civilDayToPicker(day) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  if (!match) throw new Error("Data inválida");
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12);
  if (pickerToCivilDay(date) !== day) throw new Error("Data inválida");
  return date;
}
export function pickerToCivilDay(date) {
  const pad = (v) => String(v).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

// Resolve a São Paulo wall time using IANA transitions, never a fixed UTC offset.
// Reject gaps and repeated times instead of guessing which instant was intended.
export function brasiliaCivilToInstant(day, time) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  const t = /^(\d{2}):(\d{2}):(\d{2})$/.exec(time);
  if (!m || !t) throw new Error("Data ou horário inválido");
  const [y, mo, d, h, mi, s] = [...m.slice(1), ...t.slice(1)].map(Number);
  const wall = Date.UTC(y, mo - 1, d, h, mi, s);
  const check = new Date(wall);
  if (y < 100 || check.getUTCFullYear() !== y || check.getUTCMonth() !== mo - 1 || check.getUTCDate() !== d || h > 23 || mi > 59 || s > 59) throw new Error("Data ou horário inválido");
  const offsets = new Set();
  for (const delta of [-172800000, -86400000, 0, 86400000, 172800000]) {
    const sample = wall + delta;
    const p = parts(new Date(sample));
    offsets.add(Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second) - sample);
  }
  const candidates = [...offsets].map((offset) => wall - offset).filter((instant) => {
    const p = parts(new Date(instant));
    return `${p.year}-${p.month}-${p.day}` === day && `${p.hour}:${p.minute}:${p.second}` === time;
  });
  if (candidates.length !== 1) throw new Error("Horário inexistente ou ambíguo em Brasília");
  return new Date(candidates[0]);
}

export const formatDateForMongoDB = (date) => date.toISOString();
// Accept only explicit timezone designators; never guess a naive legacy value.
export function parseExplicitInstant(value) {
  if (typeof value !== "string" || !(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) || /\b(?:GMT|UTC)$/i.test(value))) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}
export function formatBrasiliaDateTime(value) {
  const date = parseExplicitInstant(value);
  return date ? new Intl.DateTimeFormat("pt-BR", { timeZone: RESERVATION_ZONE, dateStyle: "short", timeStyle: "short" }).format(date) : "Data/horário sem fuso definido — confirme a reserva";
}
export function formatReservation(start, end) {
  const startAt = parseExplicitInstant(start), endAt = parseExplicitInstant(end);
  const date = (d) => new Intl.DateTimeFormat("pt-BR", { timeZone: RESERVATION_ZONE }).format(d);
  const time = (d) => new Intl.DateTimeFormat("pt-BR", { timeZone: RESERVATION_ZONE, hour: "2-digit", minute: "2-digit" }).format(d);
  return {
    day: startAt ? date(startAt) : (start ? "Fuso indefinido — confirme" : "Indefinido"),
    hours: startAt && endAt ? `${time(startAt)} - ${time(endAt)}${date(startAt) !== date(endAt) ? ` (${date(endAt)})` : ""}` : (start || end ? "Fuso indefinido — confirme" : "Indefinido"),
  };
}
