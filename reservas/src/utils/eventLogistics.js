// Rules of the logistics step (issue #35): the auxiliary text of "Trilha
// empreendedora" and "Projeto Extensão" is only used, and then required, when
// the matching selector is "Sim".
export const isYes = (selection) => selection === "sim";

export const descriptionDisabled = (selection) => !isYes(selection);

export function validateLogistics(formData) {
  const errors = {};
  if (isYes(formData.trilha) && !String(formData.trilhaDesc ?? "").trim()) {
    errors.trilhaDesc = "Descreva a trilha empreendedora.";
  }
  if (isYes(formData.projeto) && !String(formData.projetoDesc ?? "").trim()) {
    errors.projetoDesc = "Descreva o projeto de extensão.";
  }
  return errors;
}

// Switching a selector away from "Sim" drops the text typed for it, so a stale
// description is never sent with "Não".
export function staleDescriptionReset(name, value) {
  if (name === "trilha" && !isYes(value)) return { name: "trilhaDesc", value: "" };
  if (name === "projeto" && !isYes(value)) return { name: "projetoDesc", value: "" };
  return null;
}
