// Triagem de pedido de reserva contra o procedimento da Assessoria Acadêmica.
// Encadeamento para a frente: fatos informados geram fatos derivados, que geram
// outros, até não haver mais o que derivar. Fato que não pôde ser derivado fica
// ausente e a regra que depende dele devolve "indeterminada", nunca "atende".
// Nenhuma regra foi validada pela Assessoria ainda (`validadaPor: null`).
import { STATUS } from "./motor.js";

export const TURNOS = Object.freeze(["matutino", "vespertino", "noturno"]);
export const LIMITES = Object.freeze({ porDia: 2, porSolicitante: 6 });
const FONTE = "Procedimento da Assessoria Acadêmica, 28/09";
const INFORMADO = "informado no pedido";

const dataValida = (s) => {
  if (typeof s !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(`${s}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
};

export const DERIVACOES = Object.freeze([
  {
    id: "valida-linhas",
    produz: "linhas_validas",
    depende: ["linhas"],
    calcula: ({ linhas }) => {
      const vistas = new Set();
      return linhas.valor.every((l) => {
        const chave = `${l.data}|${l.turno}`;
        const ok = dataValida(l.data) && TURNOS.includes(l.turno) && !vistas.has(chave);
        vistas.add(chave);
        return ok;
      });
    },
  },
  {
    id: "lista-faltas",
    produz: "campos_faltantes",
    depende: ["linhas"],
    calcula: ({ participantes, linhas }) => {
      const faltam = [];
      if (!participantes || !Number.isInteger(participantes.valor) || participantes.valor < 1) faltam.push("participantes");
      if (linhas.valor.length === 0) faltam.push("datas e turnos");
      return faltam;
    },
  },
  {
    id: "confere-completo",
    produz: "pedido_completo",
    depende: ["campos_faltantes", "linhas_validas"],
    calcula: ({ campos_faltantes, linhas_validas }) => campos_faltantes.valor.length === 0 && linhas_validas.valor,
  },
  {
    id: "conta-por-dia",
    produz: "reservas_no_dia",
    depende: ["linhas", "pedido_completo"],
    quando: ({ pedido_completo }) => pedido_completo.valor === true,
    calcula: ({ linhas }) => linhas.valor.reduce((acc, l) => ({ ...acc, [l.data]: (acc[l.data] || 0) + 1 }), {}),
  },
  {
    id: "confere-dia",
    produz: "dia_ok",
    depende: ["reservas_no_dia"],
    calcula: ({ reservas_no_dia }) => Object.values(reservas_no_dia.valor).every((n) => n <= LIMITES.porDia),
  },
  {
    id: "conta-total",
    produz: "total",
    depende: ["linhas", "pedido_completo"],
    quando: ({ pedido_completo }) => pedido_completo.valor === true,
    calcula: ({ linhas }) => linhas.valor.length,
  },
  {
    id: "confere-total",
    produz: "total_ok",
    depende: ["total"],
    calcula: ({ total }) => total.valor <= LIMITES.porSolicitante,
  },
]);

export function encadear(base, derivacoes = DERIVACOES) {
  const fatos = { ...base };
  const cadeia = [];
  let mudou = true;
  while (mudou) {
    mudou = false;
    for (const d of derivacoes) {
      if (fatos[d.produz] || !d.depende.every((k) => fatos[k] !== undefined)) continue;
      if (d.quando && !d.quando(fatos)) continue;
      fatos[d.produz] = { valor: d.calcula(fatos), fonte: `derivado (${d.id})`, derivadoDe: d.depende };
      cadeia.push({ regra: d.id, produz: d.produz, valor: fatos[d.produz].valor, deDe: d.depende });
      mudou = true;
    }
  }
  return { fatos, cadeia };
}

const pend = (motivo) => ({ status: STATUS.INDETERMINADA, motivo });
const atende = (motivo, fatos) => ({ status: STATUS.ATENDE, motivo, fatos });
const viola = (motivo, fatos) => ({ status: STATUS.NAO_ATENDE, motivo, fatos });

export const REGRAS_TRIAGEM = Object.freeze([
  {
    id: "periodo",
    descricao: "Cada linha é um período: uma data válida e um dos três turnos, sem repetir.",
    fonte: FONTE,
    validadaPor: null,
    avalia({ linhas, linhas_validas }) {
      if (!linhas || linhas.valor.length === 0) return pend("nenhuma data e turno informados");
      return linhas_validas.valor
        ? atende(`${linhas.valor.length} período(s) válido(s)`, ["linhas_validas"])
        : viola("há data inválida, turno desconhecido ou período repetido", ["linhas_validas"]);
    },
  },
  {
    id: "completo",
    descricao: "O pedido traz participantes, datas e turnos.",
    fonte: FONTE,
    validadaPor: null,
    avalia({ campos_faltantes, pedido_completo }) {
      if (pedido_completo?.valor) return atende("pedido completo", ["pedido_completo"]);
      const faltas = campos_faltantes?.valor ?? [];
      return pend(faltas.length ? `falta: ${faltas.join(", ")}` : "há períodos inválidos; veja a regra do período");
    },
  },
  {
    id: "max-por-dia",
    descricao: `No máximo ${LIMITES.porDia} reservas por dia.`,
    fonte: FONTE,
    validadaPor: null,
    avalia({ reservas_no_dia, dia_ok }) {
      if (!dia_ok) return pend("depende do pedido completo e válido");
      if (dia_ok.valor) return atende(`maior número num dia: ${Math.max(...Object.values(reservas_no_dia.valor))} (limite ${LIMITES.porDia})`, ["reservas_no_dia", "dia_ok"]);
      const acima = Object.entries(reservas_no_dia.valor).filter(([, n]) => n > LIMITES.porDia).map(([d, n]) => `${d} (${n})`);
      return viola(`acima do limite de ${LIMITES.porDia} em: ${acima.join(", ")}`, ["reservas_no_dia", "dia_ok"]);
    },
  },
  {
    id: "max-total",
    descricao: `No máximo ${LIMITES.porSolicitante} reservas por solicitante.`,
    fonte: FONTE,
    validadaPor: null,
    avalia({ total, total_ok }) {
      if (!total_ok) return pend("depende do pedido completo e válido");
      return total_ok.valor
        ? atende(`${total.valor} reserva(s) (limite ${LIMITES.porSolicitante})`, ["total", "total_ok"])
        : viola(`${total.valor} reservas, acima do limite de ${LIMITES.porSolicitante}`, ["total", "total_ok"]);
    },
  },
  {
    id: "excecao",
    descricao: "Caso excepcional é encaminhado à Assessoria, que decide.",
    fonte: FONTE,
    validadaPor: null,
    avalia({ excecao }) {
      return excecao?.valor
        ? pend("caso excepcional declarado: quem decide é a Assessoria")
        : atende("sem pedido de exceção", ["excecao"]);
    },
  },
]);

const AVISOS = Object.freeze(["A reserva só vale após a confirmação formal da Assessoria, sujeita a disponibilidade e prioridade."]);

export function triar(pedido, derivacoes = DERIVACOES) {
  const base = { linhas: { valor: (pedido.linhas || []).map((l) => ({ ...l })), fonte: INFORMADO }, excecao: { valor: Boolean(pedido.excecao), fonte: INFORMADO } };
  if (Number.isInteger(pedido.participantes)) base.participantes = { valor: pedido.participantes, fonte: INFORMADO };
  const { fatos, cadeia } = encadear(base, derivacoes);
  const justificativas = REGRAS_TRIAGEM.map((r) => {
    const resultado = r.avalia(fatos);
    return {
      regra: r.id,
      descricao: r.descricao,
      fonteRegra: r.fonte,
      regraValidada: Boolean(r.validadaPor),
      ...resultado,
      fatos: (resultado.fatos || []).map((id) => ({ id, valor: fatos[id].valor, fonte: fatos[id].fonte })),
    };
  });
  const conclusao = base.excecao.valor
    ? "assessoria"
    : justificativas.some((j) => j.status === STATUS.NAO_ATENDE)
      ? "viola"
      : justificativas.some((j) => j.status === STATUS.INDETERMINADA)
        ? "incompleto"
        : "dentro";
  return {
    conclusao,
    justificativas,
    cadeia,
    avisos: [...AVISOS],
    regrasNaoValidadas: REGRAS_TRIAGEM.filter((r) => !r.validadaPor).map((r) => r.id),
  };
}
