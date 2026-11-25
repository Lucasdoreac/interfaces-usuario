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

// Controla o carregamento paginado de uma lista de salas para UM filtro por vez.
// Cada mudança de filtro incrementa uma sequência; respostas, erros e a liberação
// do guard de pedidos que não pertencem à sequência atual são descartados, assim
// um pedido antigo não sobrescreve salas nem avança page/hasMore do filtro novo.
// O guard "há pedido em andamento" é variável da própria instância (não um valor
// de closure do render), então nunca fica velho.
export function createRoomsLoader({ fetchPage, onChange }) {
  let sequence = 0;
  let inFlight = false;
  let filter = null;
  let state = { rooms: [], page: 1, hasMore: true, error: null, isLoading: false };

  const update = (patch) => {
    state = { ...state, ...patch };
    onChange(state);
  };

  async function load() {
    if (inFlight) return;
    const mine = sequence;
    const currentPage = state.page;
    inFlight = true;
    update({ isLoading: true, error: null });
    try {
      const response = await fetchPage(currentPage, filter);
      if (mine !== sequence) return;
      if (response && Array.isArray(response.data)) {
        const newRooms = response.data;
        const more = hasMoreRoomPages(newRooms, response.pagination, currentPage);
        update({
          rooms: currentPage === 1 ? newRooms : [...state.rooms, ...newRooms],
          page: more ? currentPage + 1 : state.page,
          hasMore: more,
        });
      } else {
        update({ hasMore: false });
      }
    } catch (error) {
      if (mine !== sequence) return;
      update({ error: roomLoadErrorMessage(error), hasMore: false });
    } finally {
      if (mine === sequence) {
        inFlight = false;
        update({ isLoading: false });
      }
    }
  }

  return {
    // Novo filtro: descarta o que estava em andamento e recarrega a página 1.
    setFilter(next) {
      sequence += 1;
      inFlight = false;
      filter = next;
      state = { rooms: [], page: 1, hasMore: true, error: null, isLoading: false };
      onChange(state);
      return load();
    },
    loadMore() {
      if (state.hasMore && !state.error) return load();
      return undefined;
    },
    // Tentar novamente: repete a página que falhou para o filtro atual (página 1 se
    // nenhuma sala foi carregada; senão a próxima, anexando).
    retry() {
      if (!state.error) return undefined;
      state = { ...state, error: null, hasMore: true };
      return load();
    },
    // Invalida pedidos pendentes (desmontagem ou troca de filtro).
    cancel() {
      sequence += 1;
      inFlight = false;
    },
  };
}
