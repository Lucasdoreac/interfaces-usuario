import test from 'node:test';
import assert from 'node:assert/strict';
import { carregarSala } from '../../src/especialista/catalogo.js';
import { localizacao } from '../../src/especialista/motor.js';

test('adapta apenas fatos existentes: campus entra, capacidade não', async () => {
  const salas = await carregarSala({ http: { get: async () => ({ status: 200, data: { id: '1', name: 'A', campus: 'c1', capacidade: 999 } }) } }, '1');
  assert.deepEqual(salas, [{ id: '1', rotulo: 'A', fatos: { campus: { valor: 'c1', fonte: 'catálogo /rooms', confirmadoEm: null } } }]);
  assert.deepEqual(localizacao(salas[0]).ausentes, ['predio', 'andar']);
});

test('ID vazio e sala incompleta são recusados', async () => {
  await assert.rejects(carregarSala({ http: { get: async () => ({}) } }, ' '), /Informe o ID/);
  await assert.rejects(carregarSala({ http: { get: async () => ({ status: 200, data: { id: '1' } }) } }, '1'), /vazia ou incompleta/);
});
