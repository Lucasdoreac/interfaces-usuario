import test from "node:test";
import assert from "node:assert/strict";
import { ATIVIDADES, CASOS_DE_USO, CLASSES, COMPONENTES, SEQUENCIA, TECNOLOGIAS } from "../../src/especialista/diagramas.js";
import { localizacao, recomendar } from "../../src/especialista/motor.js";

const gerais = [CASOS_DE_USO, COMPONENTES, CLASSES, ATIVIDADES];

test("toda ligação aponta para elementos que existem e cada diagrama tem versão em texto", () => {
  for (const d of gerais) {
    const ids = new Set(d.elementos.map((e) => e.id));
    assert.equal(ids.size, d.elementos.length, `ids repetidos em ${d.id}`);
    for (const l of d.ligacoes) assert.ok(ids.has(l.de) && ids.has(l.para), `${d.id}: ${l.de}->${l.para}`);
    assert.ok(d.alternativa && d.legenda && d.titulo);
  }
  for (const m of SEQUENCIA.mensagens) {
    assert.ok(SEQUENCIA.participantes[m.de] && SEQUENCIA.participantes[m.para], m.texto);
  }
});

test("classes: Resultado e Localizacao listam os campos que o motor realmente devolve", () => {
  const linhas = (id) => CLASSES.elementos.find((e) => e.id === id).linhas;
  const resultado = Object.keys(recomendar([], {}));
  assert.deepEqual([...linhas("res")].sort(), [...resultado].sort());
  const loc = Object.keys(localizacao({ id: "x", rotulo: "x" })).filter((k) => k !== "salaId" && k !== "rotulo");
  assert.deepEqual(linhas("loc").map((l) => l.split(" ")[0]).sort(), loc.sort());
});

test("componentes incluem o RabbitMQ do limitador do catálogo (compose.yaml)", () => {
  assert.ok(COMPONENTES.elementos.some((e) => /rabbitmq/i.test(`${e.titulo} ${(e.linhas || []).join(" ")}`)));
});

test("atividades descrevem a precedência real: não atende > indeterminada > atende, e semCriterio", () => {
  const texto = JSON.stringify(ATIVIDADES.elementos);
  for (const termo of ["semCriterio", "indeterminada", "rejeitada", "recomendada"]) assert.match(texto, new RegExp(termo));
});

test("tecnologias: cada camada cita arquivo:linha e a IDE fica para o Lucas preencher", () => {
  for (const t of TECNOLOGIAS.filter((x) => x.camada !== "Ferramentas")) {
    assert.match(t.onde, /\.\w+:\d+/, `${t.camada} sem arquivo:linha`);
  }
  const f = TECNOLOGIAS.find((x) => x.camada === "Ferramentas");
  assert.match(f.itens, /IDE: a preencher pelo Lucas/);
  assert.doesNotMatch(f.itens, /dia/);
});
