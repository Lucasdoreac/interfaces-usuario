// Dados SINTÉTICOS para demonstração e testes. Não descrevem salas reais da UDF.
// Os rótulos imitam o formato do catálogo (número, "LAB n", "T-nn"); prédio, andar,
// capacidade e recursos não existem no catálogo real e aqui servem só de cenário.
const sint = (valor) => ({ valor, fonte: "sintetico", confirmadoEm: null });

export const SALAS_SINTETICAS = Object.freeze([
  { id: "s1", rotulo: "SINT-101", sintetico: true, fatos: { campus: sint("Sede"), predio: sint("Bloco A"), andar: sint(1), capacidade: sint(40), recursos: sint(["projetor"]) } },
  { id: "s2", rotulo: "SINT-LAB 1", sintetico: true, fatos: { campus: sint("Sede"), predio: sint("Bloco A"), capacidade: sint(25), recursos: sint(["projetor", "computadores"]) } },
  { id: "s3", rotulo: "SINT-T-10", sintetico: true, fatos: { campus: sint("Rezende"), capacidade: sint(80), recursos: sint(["projetor"]) } },
  { id: "s4", rotulo: "SINT-205", sintetico: true, fatos: { campus: sint("Sede") } },
]);
