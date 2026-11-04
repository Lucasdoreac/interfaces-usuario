// A API /rooms consulta uma sala por ID; seus campos físicos não são inferidos.
export async function carregarSala(api, roomId) {
  if (typeof roomId !== 'string' || !roomId.trim()) throw new Error('Informe o ID da sala.');
  const resposta = await api.http.get('/rooms', { params: { roomId: roomId.trim() } });
  const sala = resposta?.data;
  if (resposta?.status !== 200 || !sala || typeof sala.id !== 'string' || !sala.id || typeof sala.name !== 'string' || !sala.name.trim()) {
    throw new Error('A API retornou uma sala vazia ou incompleta.');
  }
  const fatos = {};
  if (typeof sala.campus === 'string' && sala.campus.trim()) {
    fatos.campus = { valor: sala.campus, fonte: 'catálogo /rooms', confirmadoEm: null };
  }
  return [{ id: sala.id, rotulo: sala.name, fatos }];
}
