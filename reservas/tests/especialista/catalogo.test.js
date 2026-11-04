import test from 'node:test';
import assert from 'node:assert/strict';
import { carregarSala } from '../../src/especialista/catalogo.js';
import { recomendar } from '../../src/especialista/motor.js';

test('adapta apenas fatos existentes e não recomenda por capacidade ausente', async () => {
  const salas = await carregarSala({ http: { get: async () => ({ status: 200, data: { id: '1', name: 'A', campus: 'c1', capacidade: 999 } }) } }, '1');
  assert.deepEqual(salas, [{ id: '1', rotulo: 'A', fatos: { campus: { valor: 'c1', fonte: 'catálogo /rooms', confirmadoEm: null } } }]);
  assert.equal(recomendar(salas, { participantes: 10 }).recomendadas.length, 0);
  assert.equal(recomendar(salas, { participantes: 10 }).indeterminadas.length, 1);
});

test('resposta vazia ou sem campos obrigatórios é erro explícito', async () => {
  for (const data of [null, {}, { id: '1', campus: 'c' }]) {
    await assert.rejects(carregarSala({ http: { get: async () => ({status: 200, data}) } }, '1'));
  }
});

test('campus ausente continua ausente', async () => {
  const [sala] = await carregarSala({ http: { get: async () => ({ status: 200, data: { id: '1', name: 'A' } }) } }, '1');
  assert.deepEqual(sala.fatos, {});
  assert.equal(recomendar([sala], { campus: 'c' }).indeterminadas.length, 1);
});

test('propaga erro HTTP e consulta o ID informado', async () => {
  let params;
  await assert.rejects(carregarSala({ http: { get: async (path, config) => { assert.equal(path, '/rooms'); params = config.params; throw new Error('HTTP 403'); } } }, '1'), /HTTP 403/);
  assert.deepEqual(params, { roomId: '1' });
});
