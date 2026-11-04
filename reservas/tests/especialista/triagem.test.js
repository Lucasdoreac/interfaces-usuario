import test from "node:test";
import assert from "node:assert/strict";
import { DERIVACOES, REGRAS_TRIAGEM, TURNOS, encadear, triar } from "../../src/especialista/triagem.js";

const L = (data, turno) => ({ data, turno });
const pedido = (linhas, extra = {}) => ({ participantes: 30, linhas, ...extra });
const status = (r, id) => r.justificativas.find((j) => j.regra === id).status;

test("pedido dentro das regras: 2 reservas no dia e 3 no total, sem exceção", () => {
  const r = triar(pedido([L("2026-12-01", "matutino"), L("2026-12-01", "noturno"), L("2026-12-02", "vespertino")]));
  assert.equal(r.conclusao, "dentro");
  for (const id of ["periodo", "completo", "max-por-dia", "max-total"]) assert.equal(status(r, id), "atende", id);
});

test("encadeamento: reservas_no_dia leva a dia_ok, e a cadeia registra de quais fatos veio", () => {
  const { fatos, cadeia } = encadear({
    participantes: { valor: 10, fonte: "informado no pedido" },
    linhas: { valor: [L("2026-12-01", "matutino"), L("2026-12-01", "vespertino"), L("2026-12-01", "noturno")], fonte: "informado no pedido" },
    excecao: { valor: false, fonte: "informado no pedido" },
  });
  assert.equal(fatos.dia_ok.valor, false);
  const passo = cadeia.find((c) => c.produz === "dia_ok");
  assert.deepEqual(passo.deDe, ["reservas_no_dia"]);
  assert.ok(cadeia.findIndex((c) => c.produz === "reservas_no_dia") < cadeia.findIndex((c) => c.produz === "dia_ok"));
});

test("3 reservas no mesmo dia violam o limite de 2 por dia e a justificativa cita a fonte", () => {
  const r = triar(pedido(TURNOS.map((t) => L("2026-12-01", t))));
  assert.equal(r.conclusao, "viola");
  const j = r.justificativas.find((x) => x.regra === "max-por-dia");
  assert.equal(j.status, "nao_atende");
  assert.match(j.motivo, /2026-12-01/);
  assert.match(j.fonteRegra, /Assessoria/);
});

test("7 reservas no total violam o limite de 6 por solicitante", () => {
  const dias = ["01", "02", "03", "04"].map((d) => `2026-12-${d}`);
  const linhas = [...dias.map((d) => L(d, "matutino")), ...dias.slice(0, 3).map((d) => L(d, "noturno"))];
  const r = triar(pedido(linhas));
  assert.equal(status(r, "max-total"), "nao_atende");
  assert.equal(status(r, "max-por-dia"), "atende");
  assert.equal(r.conclusao, "viola");
});

test("pedido incompleto não vira 'dentro': falta dado e as regras que dependem ficam indeterminadas", () => {
  const r = triar({ participantes: undefined, linhas: [L("2026-12-01", "matutino")] });
  assert.equal(r.conclusao, "incompleto");
  assert.equal(status(r, "completo"), "indeterminada");
  assert.equal(status(r, "max-por-dia"), "indeterminada");
  assert.match(r.justificativas.find((j) => j.regra === "completo").motivo, /participantes/);
  assert.equal(triar(pedido([])).conclusao, "incompleto");
});

test("data inválida, turno desconhecido ou linha repetida violam a regra do período", () => {
  for (const linhas of [[L("2026-02-31", "matutino")], [L("2026-12-01", "madrugada")], [L("2026-12-01", "matutino"), L("2026-12-01", "matutino")]]) {
    const r = triar(pedido(linhas));
    assert.equal(status(r, "periodo"), "nao_atende", JSON.stringify(linhas));
    assert.equal(r.conclusao, "viola");
  }
});

test("exceção declarada vai para a Assessoria, mesmo violando limites, e a violação continua listada", () => {
  const r = triar(pedido(TURNOS.map((t) => L("2026-12-01", t)), { excecao: true }));
  assert.equal(r.conclusao, "assessoria");
  assert.equal(status(r, "max-por-dia"), "nao_atende");
  assert.match(r.avisos.join(" "), /confirmação formal/);
});

test("todas as regras têm fonte documental e seguem sem validação da Assessoria", () => {
  assert.ok(REGRAS_TRIAGEM.length >= 5);
  for (const g of REGRAS_TRIAGEM) {
    assert.match(g.fonte, /Procedimento da Assessoria Acadêmica, 28\/09/);
    assert.equal(g.validadaPor, null);
  }
  const r = triar(pedido([L("2026-12-01", "matutino")]));
  assert.deepEqual(r.regrasNaoValidadas.sort(), REGRAS_TRIAGEM.map((g) => g.id).sort());
});

test("revert-check: sem a derivação dia_ok a regra não finge atender", () => {
  const sem = DERIVACOES.filter((d) => d.produz !== "dia_ok");
  const r = triar(pedido([L("2026-12-01", "matutino")]), sem);
  assert.equal(status(r, "max-por-dia"), "indeterminada");
  assert.notEqual(r.conclusao, "dentro");
});

test("a triagem não altera o pedido recebido", () => {
  const p = pedido([L("2026-12-01", "matutino")]);
  const antes = JSON.stringify(p);
  triar(p);
  assert.equal(JSON.stringify(p), antes);
});
