export const LOGOUT_UNCONFIRMED_MESSAGE =
  "Você saiu neste navegador, mas não conseguimos confirmar o encerramento da sessão no servidor. Ela expira sozinha em até 12 horas.";

// Estado de navegação para a tela de login depois de "Sair". A saída local acontece
// sempre; só quando o servidor não confirmou (resultado diferente de true) a tela
// recebe o aviso. Só uma flag booleana viaja: nunca o token.
export function logoutNavigationState(confirmed) {
  return confirmed === true ? { loggedOut: true } : { loggedOut: true, logoutUnconfirmed: true };
}

export function logoutNoticeFrom(state) {
  return state?.logoutUnconfirmed === true ? LOGOUT_UNCONFIRMED_MESSAGE : "";
}
