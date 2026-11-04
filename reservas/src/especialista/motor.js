// Motor de regras da recomendação de salas.
// Cada fato de uma sala é { valor, fonte, confirmadoEm } ou ausente. O motor nunca
// presume um fato ausente: a regra que dependeria dele devolve "indeterminada".
// Regras só valem como política da instituição quando `validadaPor` está preenchido.

export const STATUS = Object.freeze({
  ATENDE: "atende",
  NAO_ATENDE: "nao_atende",
  INDETERMINADA: "indeterminada",
});

export function fato(sala, campo) {
  const f = sala?.fatos?.[campo];
  return f && f.valor !== undefined && f.valor !== null && f.valor !== "" ? f : null;
}

export const REGRAS = Object.freeze([
  {
    id: "capacidade",
    descricao: "A capacidade da sala deve comportar o número de participantes.",
    fonte: "regra-sintetica",
    validadaPor: null,
    aplica: (pedido) => Number.isInteger(pedido.participantes),
    avalia(sala, pedido) {
      const f = fato(sala, "capacidade");
      if (!f) return { status: STATUS.INDETERMINADA, motivo: "capacidade não informada para a sala" };
      return f.valor >= pedido.participantes
        ? { status: STATUS.ATENDE, motivo: `capacidade ${f.valor} comporta ${pedido.participantes}`, fato: f }
        : { status: STATUS.NAO_ATENDE, motivo: `capacidade ${f.valor} não comporta ${pedido.participantes}`, fato: f };
    },
  },
  {
    id: "recursos",
    descricao: "A sala deve ter todos os recursos solicitados.",
    fonte: "regra-sintetica",
    validadaPor: null,
    aplica: (pedido) => Array.isArray(pedido.recursos) && pedido.recursos.length > 0,
    avalia(sala, pedido) {
      const f = fato(sala, "recursos");
      if (!f) return { status: STATUS.INDETERMINADA, motivo: "recursos não informados para a sala" };
      const faltam = pedido.recursos.filter((r) => !f.valor.includes(r));
      return faltam.length === 0
        ? { status: STATUS.ATENDE, motivo: "tem todos os recursos pedidos", fato: f }
        : { status: STATUS.NAO_ATENDE, motivo: `falta: ${faltam.join(", ")}`, fato: f };
    },
  },
  {
    id: "campus",
    descricao: "A sala deve estar no campus pedido.",
    fonte: "regra-sintetica",
    validadaPor: null,
    aplica: (pedido) => Boolean(pedido.campus),
    avalia(sala, pedido) {
      const f = fato(sala, "campus");
      if (!f) return { status: STATUS.INDETERMINADA, motivo: "campus não informado para a sala" };
      return f.valor === pedido.campus
        ? { status: STATUS.ATENDE, motivo: `está no campus ${f.valor}`, fato: f }
        : { status: STATUS.NAO_ATENDE, motivo: `está no campus ${f.valor}`, fato: f };
    },
  },
]);

function avaliarSala(sala, pedido, regras) {
  const justificativas = regras
    .filter((r) => r.aplica(pedido))
    .map((r) => ({
      regra: r.id,
      fonteRegra: r.fonte,
      regraValidada: Boolean(r.validadaPor),
      ...r.avalia(sala, pedido),
    }));
  const status = justificativas.some((j) => j.status === STATUS.NAO_ATENDE)
    ? STATUS.NAO_ATENDE
    : justificativas.some((j) => j.status === STATUS.INDETERMINADA)
      ? STATUS.INDETERMINADA
      : STATUS.ATENDE;
  return { salaId: sala.id, rotulo: sala.rotulo, status, justificativas };
}

// Separa as salas em recomendadas (todas as regras aplicáveis atendidas), as que
// dependem de dado ausente e as rejeitadas. Sem nenhuma regra aplicável, nada é
// recomendado: a ausência de critério não é aprovação.
export function recomendar(salas, pedido, regras = REGRAS) {
  const aplicaveis = regras.filter((r) => r.aplica(pedido));
  const avaliadas = salas.map((s) => avaliarSala(s, pedido, regras));
  const semCriterio = aplicaveis.length === 0;
  return {
    semCriterio,
    regrasNaoValidadas: aplicaveis.filter((r) => !r.validadaPor).map((r) => r.id),
    recomendadas: semCriterio ? [] : avaliadas.filter((a) => a.status === STATUS.ATENDE),
    indeterminadas: semCriterio ? [] : avaliadas.filter((a) => a.status === STATUS.INDETERMINADA),
    rejeitadas: semCriterio ? [] : avaliadas.filter((a) => a.status === STATUS.NAO_ATENDE),
  };
}

// Localização é informação, não recomendação: só devolve o que está confirmado e
// lista explicitamente o que falta. Nunca monta trajeto.
export function localizacao(sala) {
  const campos = ["campus", "predio", "andar"];
  const conhecidos = {};
  const ausentes = [];
  for (const campo of campos) {
    const f = fato(sala, campo);
    if (f) conhecidos[campo] = { valor: f.valor, fonte: f.fonte, confirmadoEm: f.confirmadoEm ?? null };
    else ausentes.push(campo);
  }
  return { salaId: sala.id, rotulo: sala.rotulo, conhecidos, ausentes, trajeto: null };
}
