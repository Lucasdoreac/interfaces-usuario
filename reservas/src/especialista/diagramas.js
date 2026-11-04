// Diagramas UML do sistema especialista, como dados. Cada um descreve só o que
// existe no código: a SPA em reservas/, o motor em src/especialista/ e a API
// Flask (rotas /auth, /rooms, /courses, /types, /events, /reservations).
export const CASOS_DE_USO = {
  id: "uml-casos-de-uso",
  titulo: "Casos de uso",
  legenda: "Tracejado: validação ainda não implementada. Pedido de reserva: fluxo existente fora da demonstração.",
  largura: 760,
  altura: 400,
  fronteira: { x: 190, y: 20, w: 380, h: 360, rotulo: "Reservas e protótipo especialista" },
  elementos: [
    { id: "sol", forma: "ator", x: 70, y: 140, rotulo: "Solicitante" },
    { id: "ass", forma: "ator", x: 690, y: 90, rotulo: "Assessoria Acadêmica" },
    { id: "reg", forma: "ator", x: 690, y: 290, rotulo: "Responsável pelas regras" },
    { id: "u1", forma: "elipse", x: 230, y: 70, w: 300, h: 44, rotulo: "Informar a necessidade do evento" },
    { id: "u2", forma: "elipse", x: 230, y: 135, w: 300, h: 44, rotulo: "Receber recomendação justificada" },
    { id: "u3", forma: "elipse", x: 230, y: 200, w: 300, h: 44, rotulo: "Consultar localização confirmada" },
    { id: "u4", forma: "elipse", x: 230, y: 265, w: 300, h: 44, rotulo: "Pedir reserva (fluxo atual)" },
    { id: "u5", forma: "elipse", x: 230, y: 330, w: 300, h: 44, rotulo: "Validar regras e fatos das salas", tracejado: true },
  ],
  ligacoes: [
    { de: "sol", para: "u1" }, { de: "sol", para: "u2" }, { de: "sol", para: "u3" }, { de: "sol", para: "u4" },
    { de: "ass", para: "u4" }, { de: "reg", para: "u5" },
  ],
  alternativa: "O Solicitante informa o evento, recebe a recomendação com justificativa, consulta a localização e pede a reserva. A Assessoria Acadêmica participa do fluxo de reserva existente, fora da demonstração. O Responsável pelas regras valida regras e fatos das salas (ainda não implementado).",
};

export const COMPONENTES = {
  id: "uml-componentes",
  titulo: "Componentes",
  legenda: "Setas: quem chama quem. O módulo do especialista roda no navegador e não grava nada.",
  largura: 760,
  altura: 360,
  elementos: [
    { id: "spa", forma: "caixa", x: 20, y: 20, w: 250, h: 150, titulo: "SPA Reservas", linhas: ["React 19 + React Router 8", "páginas e formulário de evento", "especialista/motor.js (puro)", "especialista/documentacao.js"] },
    { id: "api", forma: "caixa", x: 330, y: 20, w: 200, h: 110, titulo: "API Reservas", linhas: ["Flask (Python 3.12+)", "/rooms /events /reservations", "/auth /courses /types"] },
    { id: "cat", forma: "caixa", x: 570, y: 20, w: 170, h: 90, titulo: "shared-resources", linhas: ["Auth e catálogo", "Flask, GraphQL, Redis"] },
    { id: "db", forma: "caixa", x: 330, y: 220, w: 200, h: 80, titulo: "MongoDB", linhas: ["campus, salas, ofertas", "eventos e reservas"] },
    { id: "pdf", forma: "caixa", x: 570, y: 220, w: 170, h: 90, titulo: "Typst + MinIO", linhas: ["PDF do pedido", "armazenado no bucket"] },
    { id: "mail", forma: "caixa", x: 20, y: 240, w: 250, h: 70, titulo: "Cloud Function", linhas: ["envio de e-mail de aprovação"] },
  ],
  ligacoes: [
    { de: "spa", para: "api", rotulo: "HTTP/JSON" },
    { de: "api", para: "cat", rotulo: "catálogo, login" },
    { de: "api", para: "db", rotulo: "pymongo" },
    { de: "api", para: "pdf", rotulo: "gera e guarda" },
    { de: "api", para: "mail", rotulo: "aviso ao revisor" },
  ],
  alternativa: "A SPA chama a API Reservas por HTTP. A API consulta o catálogo e o login em shared-resources, grava eventos e reservas no MongoDB, gera o PDF com Typst e guarda no MinIO, e aciona a Cloud Function para o e-mail de aprovação. O motor está na SPA; usa dados sintéticos ou, opcionalmente, uma sala consultada na API.",
};

export const CLASSES = {
  id: "uml-classes",
  titulo: "Classes do motor de regras",
  legenda: "Estrutura de src/especialista/motor.js. Fato ausente leva a 'indeterminada', nunca a 'atende'.",
  largura: 760,
  altura: 330,
  elementos: [
    { id: "sala", forma: "caixa", x: 20, y: 20, w: 210, h: 130, titulo: "Sala", linhas: ["id", "rotulo", "fatos: Fato por campo", "campo: campus, predio,", "andar, capacidade, recursos"] },
    { id: "fato", forma: "caixa", x: 20, y: 200, w: 210, h: 100, titulo: "Fato", linhas: ["valor", "fonte", "confirmadoEm"] },
    { id: "regra", forma: "caixa", x: 280, y: 20, w: 220, h: 150, titulo: "Regra", linhas: ["id", "descricao", "fonte", "validadaPor", "aplica(pedido)", "avalia(sala, pedido)"] },
    { id: "ped", forma: "caixa", x: 280, y: 215, w: 220, h: 90, titulo: "Pedido", linhas: ["participantes", "recursos[]", "campus"] },
    { id: "res", forma: "caixa", x: 550, y: 20, w: 190, h: 150, titulo: "Resultado", linhas: ["recomendadas", "indeterminadas", "rejeitadas", "semCriterio", "regrasNaoValidadas"] },
    { id: "loc", forma: "caixa", x: 550, y: 215, w: 190, h: 90, titulo: "Localizacao", linhas: ["conhecidos", "ausentes", "trajeto = null"] },
  ],
  ligacoes: [
    { de: "sala", para: "fato", rotulo: "0..*" },
    { de: "regra", para: "sala", rotulo: "avalia" },
    { de: "regra", para: "ped", rotulo: "usa" },
    { de: "sala", para: "loc", rotulo: "informa" },
  ],
  alternativa: "Uma Sala pode ter Fatos, cada um com valor e fonte. Uma Regra avalia uma Sala segundo um Pedido; recomendar agrega as avaliações no Resultado, separado em recomendadas, indeterminadas e rejeitadas. Localização é derivada da Sala e nunca tem trajeto.",
};

export const SEQUENCIA = {
  id: "uml-sequencia",
  titulo: "Sequência da recomendação",
  legenda: "Fluxo do protótipo; consulta ao catálogo é opcional e exige ID e autenticação.",
  participantes: ["Solicitante", "SPA", "Motor de regras", "API Reservas"],
  mensagens: [
    { de: 0, para: 1, texto: "informa participantes, recursos, campus" },
    { de: 1, para: 3, texto: "opcional: GET /rooms?roomId=…" },
    { de: 3, para: 1, texto: "uma sala do catálogo", tracejada: true },
    { de: 1, para: 2, texto: "recomendar(salas, pedido)" },
    { de: 2, para: 1, texto: "recomendadas, indeterminadas, rejeitadas", tracejada: true },
    { de: 1, para: 0, texto: "lista com regra, fato e fonte", tracejada: true },
  ],
  alternativa: "O Solicitante informa o evento. A SPA usa salas sintéticas ou consulta opcionalmente uma sala por ID na API; entrega os dados ao motor e mostra justificativas. A demonstração não realiza reserva.",
};

export const TECNOLOGIAS = [
  { camada: "Interface", itens: "JavaScript (ESM), React 19, React Router 8 em modo SPA sem SSR, Vite 8, Sass, Bootstrap 5", onde: "reservas/package.json e react-router.config.js" },
  { camada: "API e serviços", itens: "Python 3.12+, Flask, Gunicorn, pymongo; Auth e catálogo com Flask, GraphQL (graphene) e MongoEngine", onde: "python-services/pyproject.toml; shared-resources/internal_apis/pyproject.toml" },
  { camada: "Dados", itens: "MongoDB 8 para catálogo, eventos e reservas; Redis para cache; MinIO para os PDFs", onde: "dev-local/compose.yaml (ambiente local)" },
  { camada: "Documentos e e-mail", itens: "Typst gera o PDF do pedido; a Cloud Function envia o e-mail de aprovação", onde: "python-services/src/BLL/pdf.py e send_emails.py" },
  { camada: "Testes", itens: "node:test na interface e pytest nos serviços Python", onde: "reservas/tests; python-services/src/Tests; shared-resources/internal_apis" },
  { camada: "Execução e entrega", itens: "Docker e Docker Compose em Linux; código no GitHub; staging estático no Render", onde: "dev-local/compose.yaml; ops/staging-release.py" },
  { camada: "Ferramentas", itens: "IDE: a que o Lucas usar no dia (não registrada no repositório); controle de versão: Git", onde: "A preencher pelo Lucas" },
];
