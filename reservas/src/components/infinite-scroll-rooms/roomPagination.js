export function hasMoreRoomPages(rooms, pagination, currentPage) {
  const totalPages = pagination?.total_pages;
  return Array.isArray(rooms)
    && rooms.length > 0
    && Number.isInteger(totalPages)
    && currentPage < totalPages;
}

export function roomLoadErrorMessage(error) {
  return error?.response?.data?.error || "Erro ao carregar salas disponíveis.";
}
