export default {
  // O frontend é uma SPA; as chamadas de API continuam no serviço Flask.
  ssr: false,
  // O passo pós-build (scripts/flatten-build.mjs) move `client/*` para a raiz,
  // entregando `build/index.html` como o CRA fazia.
  buildDirectory: process.env.BUILD_DIR || "build",
};
