/** Serializes the selected instant as UTC without shifting it a second time. */
const formatDateForMongoDB = (date) => {
  return date.toISOString();
};

// Match the browser-local zone used by the scheduling picker and summary.
// API timestamps are instants: do not alter the offset when parsing.
const formatReservation = (start, end) => {
  const parse = (value) => {
    if (value == null || value === "") return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  };
  const startAt = parse(start);
  const endAt = parse(end);
  const time = (date) => date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return {
    day: startAt ? startAt.toLocaleDateString("pt-BR") : "Indefinido",
    hours: startAt && endAt ? `${time(startAt)} - ${time(endAt)}` : "Indefinido",
  };
};

export { formatDateForMongoDB, formatReservation };
