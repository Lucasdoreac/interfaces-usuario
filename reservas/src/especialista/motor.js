// Fatos e localização. Cada fato de uma sala é { valor, fonte, confirmadoEm } ou
// ausente; nunca se presume um fato ausente. A triagem de pedidos fica em triagem.js.

export const STATUS = Object.freeze({
  ATENDE: "atende",
  NAO_ATENDE: "nao_atende",
  INDETERMINADA: "indeterminada",
});

export function fato(sala, campo) {
  const f = sala?.fatos?.[campo];
  return f && f.valor !== undefined && f.valor !== null && f.valor !== "" ? f : null;
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
