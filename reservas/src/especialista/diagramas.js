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
    { id: "mq", forma: "caixa", x: 570, y: 125, w: 170, h: 80, titulo: "RabbitMQ", linhas: ["limitador de taxa do catálogo"] },
    { id: "pdf", forma: "caixa", x: 570, y: 220, w: 170, h: 90, titulo: "Typst + MinIO", linhas: ["PDF do pedido", "armazenado no bucket"] },
    { id: "mail", forma: "caixa", x: 20, y: 240, w: 250, h: 70, titulo: "Cloud Function", linhas: ["envio de e-mail de aprovação"] },
  ],
  ligacoes: [
    { de: "spa", para: "api", rotulo: "HTTP/JSON" },
    { de: "api", para: "cat", rotulo: "catálogo, login" },
    { de: "cat", para: "mq", rotulo: "limite de taxa" },
    { de: "api", para: "db", rotulo: "pymongo" },
    { de: "api", para: "pdf", rotulo: "gera e guarda" },
    { de: "api", para: "mail", rotulo: "aviso ao revisor" },
  ],
  alternativa: "A SPA chama a API Reservas por HTTP. A API consulta o catálogo e o login em shared-resources (o catálogo usa RabbitMQ para limitar a taxa de requisições), grava eventos e reservas no MongoDB, gera o PDF com Typst e guarda no MinIO, e aciona a Cloud Function para o e-mail de aprovação. O motor está na SPA; usa dados sintéticos ou, opcionalmente, uma sala consultada na API.",
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

export const ATIVIDADES = {
  id: "uml-atividades",
  titulo: "Atividades de recomendar()",
  legenda: "Fluxo de recomendar em motor.js. Fato ausente nunca vira 'atende'; sem regra aplicável nada é recomendado.",
  largura: 760,
  altura: 280,
  elementos: [
    { id: "a1", forma: "caixa", x: 20, y: 20, w: 200, h: 80, titulo: "Receber pedido e salas", linhas: ["participantes, recursos, campus"] },
    { id: "a2", forma: "caixa", x: 280, y: 20, w: 200, h: 80, titulo: "Filtrar regras aplicáveis", linhas: ["r.aplica(pedido)"] },
    { id: "a3", forma: "caixa", x: 540, y: 20, w: 200, h: 80, titulo: "Nenhuma regra aplicável?", linhas: ["semCriterio: nada é recomendado"] },
    { id: "a4", forma: "caixa", x: 20, y: 170, w: 210, h: 90, titulo: "Avaliar cada sala", linhas: ["atende, não atende ou", "indeterminada (fato ausente)"] },
    { id: "a5", forma: "caixa", x: 280, y: 170, w: 220, h: 90, titulo: "Combinar as justificativas", linhas: ["qualquer não atende: rejeitada", "senão qualquer indeterminada:", "indeterminada; senão recomendada"] },
    { id: "a6", forma: "caixa", x: 540, y: 170, w: 200, h: 90, titulo: "Devolver o resultado", linhas: ["listas por status e", "regrasNaoValidadas"] },
  ],
  ligacoes: [
    { de: "a1", para: "a2" },
    { de: "a2", para: "a3", rotulo: "se vazio" },
    { de: "a2", para: "a4", rotulo: "há regras" },
    { de: "a4", para: "a5" },
    { de: "a5", para: "a6" },
    { de: "a3", para: "a6", rotulo: "listas vazias" },
  ],
  alternativa: "Dado um pedido e as salas, o motor filtra as regras aplicáveis. Se não houver nenhuma, devolve listas vazias com semCriterio. Senão avalia cada sala em cada regra e combina: uma regra que não atende rejeita a sala; sem rejeição, um fato ausente a deixa indeterminada; só com todas atendidas ela é recomendada. O resultado lista também as regras ainda não validadas.",
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
  { camada: "Interface", itens: "JavaScript (ESM), React 19, React Router 8 em modo SPA sem SSR, Vite 8, Sass, Bootstrap 5", onde: "interfaces-usuario: reservas/package.json:5 (type module), :13 (react), :18 (react-router), :19 (sass), :10 (bootstrap), :29 (vite); reservas/react-router.config.js:3 (ssr: false)" },
  { camada: "API e serviços", itens: "Python 3.12+, Flask, Gunicorn, pymongo; Auth e catálogo com Flask, GraphQL (graphene) e MongoEngine", onde: "python-services/pyproject.toml:17 (python), :19 (flask), :24 (pymongo), :31 (gunicorn); shared-resources/internal_apis/pyproject.toml:21 (graphene), :29 (mongoengine)" },
  { camada: "Dados", itens: "MongoDB 8 para catálogo, eventos e reservas; Redis para cache; MinIO para os PDFs; RabbitMQ para o limitador de taxa do catálogo", onde: "dev-local/compose.yaml:30 (mongo:8.0), :41 (redis), :55-57 (minio), :159 (rabbitmq); shared-resources/internal_apis/pyproject.toml:34 (redis)" },
  { camada: "Documentos e e-mail", itens: "Typst gera o PDF do pedido e o MinIO o guarda; o e-mail de aprovação é pedido a uma Cloud Function por HTTP", onde: "python-services/src/BLL/pdf.py:4-5 (typst, minio); python-services/src/BLL/send_emails.py:82 (X-API-Key da função), :88 (requests.post)" },
  { camada: "Testes", itens: "node:test na interface e pytest nos serviços Python", onde: "interfaces-usuario: reservas/package.json:24 (node --test); python-services/pyproject.toml:25 (pytest); shared-resources/internal_apis/pyproject.toml:25 (pytest)" },
  { camada: "Execução e entrega", itens: "Docker e Docker Compose em Linux; código no GitHub; staging estático no Render", onde: "dev-local/compose.yaml:30 (imagens); ops/staging.Dockerfile:1 (node) e :10 (yarn build); ops/staging-release.py:26 (URL do Render)" },
  { camada: "Ferramentas", itens: "IDE: a preencher pelo Lucas; controle de versão: Git", onde: "A preencher pelo Lucas (a IDE não está registrada em nenhum repositório)" },
];
