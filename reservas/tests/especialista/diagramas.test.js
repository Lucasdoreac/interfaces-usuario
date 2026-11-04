import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { ATIVIDADES, CASOS_DE_USO, CLASSES, COMPONENTES, SEQUENCIA, TECNOLOGIAS } from "../../src/especialista/diagramas.js";
import { localizacao, recomendar } from "../../src/especialista/motor.js";

const gerais = [CASOS_DE_USO, COMPONENTES, CLASSES, ATIVIDADES];
const lerFonte = (p) => readFileSync(new URL(p, import.meta.url), "utf8");
const render = lerFonte("../../src/components/sistema-especialista/Diagrama.jsx");
const pagina = lerFonte("../../src/pages/sistema-especialista/SistemaEspecialista.jsx");
const textoDe = (d) => JSON.stringify(d);

test("toda ligação aponta para elementos que existem e cada diagrama tem versão em texto", () => {
  for (const d of gerais) {
    const ids = new Set(d.elementos.map((e) => e.id));
    assert.equal(ids.size, d.elementos.length, `ids repetidos em ${d.id}`);
    for (const l of d.ligacoes) assert.ok(ids.has(l.de) && ids.has(l.para), `${d.id}: ${l.de}->${l.para}`);
    assert.ok(d.alternativa && d.legenda && d.titulo);
  }
  for (const m of SEQUENCIA.mensagens) assert.ok(SEQUENCIA.participantes[m.de] && SEQUENCIA.participantes[m.para], m.texto);
});

test("item 1: e-mail cita o requests.post real e distingue Cloud Function de simulador local", () => {
  const t = TECNOLOGIAS.find((x) => x.camada === "Documentos e e-mail");
  assert.doesNotMatch(t.onde, /send_emails\.py:82/);
  assert.match(t.onde, /email_service\.py:73 \(URL\), :78 \(requests\.post\)/);
  assert.match(t.onde, /compose\.yaml:79/);
  assert.match(t.itens, /simulador/);
});

test("item 2: retorno (tracejada) usa ponta aberta e chamada usa ponta fechada", () => {
  assert.match(render, /seta-aberta|aberta/);
  assert.match(render, /m\.tracejada \? .*aberta/s);
});

test("item 3: fronteira nomeia só o protótipo, u4 fica fora dela e localização não promete confirmação", () => {
  const f = CASOS_DE_USO.fronteira;
  assert.doesNotMatch(f.rotulo, /Reservas/);
  const u4 = CASOS_DE_USO.elementos.find((e) => e.id === "u4");
  const dentro = u4.x >= f.x && u4.x + u4.w <= f.x + f.w && u4.y >= f.y && u4.y + u4.h <= f.y + f.h;
  assert.equal(dentro, false, "u4 (fluxo atual) deve ficar fora da fronteira");
  assert.match(u4.rotulo, /fluxo atual/);
  assert.doesNotMatch(textoDe(CASOS_DE_USO), /confirmad/i);
});

test("item 4: componentes têm «component», dependências tracejadas e evidência parcial rotulada", () => {
  for (const e of COMPONENTES.elementos) assert.equal(e.estereotipo, "component", e.id);
  for (const l of COMPONENTES.ligacoes) assert.equal(l.tracejada, true, `${l.de}->${l.para}`);
  const api2cat = COMPONENTES.ligacoes.find((l) => l.de === "api" && l.para === "cat");
  assert.match(api2cat.rotulo, /evidência parcial/);
  assert.match(textoDe(COMPONENTES), /request_methods\.py:\d+/);
  assert.match(textoDe(COMPONENTES), /\/campus/);
  const mail = COMPONENTES.elementos.find((e) => e.id === "mail");
  assert.match(textoDe(mail), /simulador/);
});

test("item 5: classes são modelo conceitual, com compartimentos e multiplicidade no extremo", () => {
  assert.match(CLASSES.titulo, /conceitual/i);
  const res = CLASSES.elementos.find((e) => e.id === "res");
  const loc = CLASSES.elementos.find((e) => e.id === "loc");
  for (const e of CLASSES.elementos) assert.ok(Array.isArray(e.atributos) && Array.isArray(e.operacoes), e.id);
  assert.deepEqual([...res.atributos].sort(), Object.keys(recomendar([], {})).sort());
  const camposLoc = Object.keys(localizacao({ id: "x", rotulo: "x" })).filter((k) => k !== "salaId" && k !== "rotulo");
  assert.deepEqual(loc.atributos.map((l) => l.split(" ")[0]).sort(), camposLoc.sort());
  const sf = CLASSES.ligacoes.find((l) => l.de === "sala" && l.para === "fato");
  assert.equal(sf.multiplicidadePara, "0..*");
  assert.equal(sf.rotulo, undefined);
});

test("item 6: atividades têm nó inicial, finais, decisões com guardas e a iteração por sala", () => {
  const formas = ATIVIDADES.elementos.map((e) => e.forma);
  assert.ok(formas.includes("inicio") && formas.includes("fim"));
  assert.ok(formas.filter((f) => f === "decisao").length >= 3);
  const guardas = ATIVIDADES.ligacoes.map((l) => l.rotulo);
  assert.ok(guardas.includes("[sim]") && guardas.includes("[não]"));
  const regiao = ATIVIDADES.elementos.find((e) => e.forma === "regiao");
  assert.match(regiao.rotulo, /para cada sala/);
  assert.match(ATIVIDADES.alternativa, /semCriterio/);
});

test("item 7: pitch marca validação como prevista, problema como hipótese e mantém 'sintéticas'", () => {
  assert.match(pagina, /validação humana das regras (está )?prevista, ainda não feita/);
  assert.match(pagina, /Hipótese a validar/);
  assert.match(pagina, /recomenda salas[^<]{0,80}sint[ée]tic/i);
  assert.doesNotMatch(pagina, /só com o que está confirmado/);
});

test("item 8: legenda da sequência cita onde o Bearer é enviado", () => {
  assert.match(SEQUENCIA.legenda, /client\.js:77-82/);
});

test("tecnologias: cada camada cita arquivo:linha e a IDE fica para o Lucas preencher", () => {
  for (const t of TECNOLOGIAS.filter((x) => x.camada !== "Ferramentas")) assert.match(t.onde, /\.\w+:\d+/, `${t.camada} sem arquivo:linha`);
  const f = TECNOLOGIAS.find((x) => x.camada === "Ferramentas");
  assert.match(f.itens, /IDE: a preencher pelo Lucas/);
});

test("classes: Localizacao e Resultado seguem o que o motor devolve", () => {
  assert.equal(Object.keys(localizacao({ id: "x" })).includes("trajeto"), true);
});
