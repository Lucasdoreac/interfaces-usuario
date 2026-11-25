// The event request wizard, in order (issue #18).
export const EVENT_STEPS = [
  { path: "/event/type-selection", label: "Tipo do evento" },
  { path: "/event/basic-info", label: "Informações básicas" },
  { path: "/event/details", label: "Detalhes" },
  { path: "/event/logistics", label: "Logística" },
  { path: "/event/schedule", label: "Data e sala" },
  { path: "/event/confirm-data", label: "Confirmação" },
];

// Where the person is in the wizard, or null outside it (login, "meus eventos",
// the final confirmation screen).
export function stepOf(pathname) {
  const index = EVENT_STEPS.findIndex(({ path }) => pathname === path || pathname.startsWith(`${path}/`));
  if (index < 0) return null;
  const total = EVENT_STEPS.length;
  return {
    current: index + 1,
    total,
    label: EVENT_STEPS[index].label,
    percent: Math.round(((index + 1) / total) * 100),
  };
}
