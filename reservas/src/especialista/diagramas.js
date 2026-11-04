// Diagramas do sistema especialista, como dados. Cada um descreve só o que existe no
// código (a SPA em reservas/, o motor em src/especialista/ e a API Flask). São
// esquemas inspirados na UML 2.5.1, não uma prova de conformidade com a norma.
export const CASOS_DE_USO = {
  id: "uml-casos-de-uso",
  titulo: "Casos de uso",
  legenda: "A fronteira é só o protótipo. Fora dela, o fluxo de reserva que já existe. Tracejado: ainda não implementado.",
  largura: 760,
  altura: 400,
  fronteira: { x: 130, y: 20, w: 340, h: 290, rotulo: "Protótipo do sistema especialista" },
  elementos: [
    { id: "sol", forma: "ator", x: 60, y: 140, rotulo: "Solicitante" },
    { id: "ass", forma: "ator", x: 690, y: 300, rotulo: "Assessoria Acadêmica" },
    { id: "reg", forma: "ator", x: 690, y: 170, rotulo: "Responsável pelas regras" },
    { id: "u1", forma: "elipse", x: 140, y: 55, w: 320, h: 44, rotulo: "Informar a necessidade do evento" },
    { id: "u2", forma: "elipse", x: 140, y: 115, w: 320, h: 44, rotulo: "Receber recomendação justificada" },
    { id: "u3", forma: "elipse", x: 140, y: 175, w: 320, h: 44, rotulo: "Ver a localização conhecida e o que falta" },
    { id: "u5", forma: "elipse", x: 140, y: 235, w: 320, h: 44, rotulo: "Validar regras e fatos das salas", tracejado: true },
    { id: "u4", forma: "elipse", x: 140, y: 335, w: 320, h: 44, rotulo: "Pedir reserva (fluxo atual, fora do protótipo)" },
  ],
  ligacoes: [
    { de: "sol", para: "u1" }, { de: "sol", para: "u2" }, { de: "sol", para: "u3" }, { de: "sol", para: "u4" },
    { de: "ass", para: "u4" }, { de: "reg", para: "u5" },
  ],
  alternativa: "Dentro do protótipo, o Solicitante informa o evento, recebe a recomendação com justificativa e vê a localização que consta nos dados, com a lista do que falta. A validação das regras e dos fatos pelo Responsável ainda não está implementada. Fora do protótipo fica o pedido de reserva, que já existe no sistema de Reservas; a Assessoria Acadêmica participa dele. A demonstração não faz reserva.",
};

export const COMPONENTES = {
  id: "uml-componentes",
  titulo: "Componentes",
  legenda: "Setas tracejadas: dependência (quem usa quem). Nem toda ligação tem a mesma evidência: veja o texto.",
  largura: 760,
  altura: 380,
  elementos: [
    { id: "spa", forma: "caixa", estereotipo: "component", x: 20, y: 20, w: 250, h: 150, titulo: "SPA Reservas", linhas: ["React 19 + React Router 8", "páginas e formulário de evento", "especialista/motor.js (puro)", "especialista/catalogo.js"] },
    { id: "api", forma: "caixa", estereotipo: "component", x: 330, y: 20, w: 190, h: 120, titulo: "API Reservas", linhas: ["Flask (Python 3.12+)", "/rooms /events /reservations", "/auth /courses /types"] },
    { id: "cat", forma: "caixa", estereotipo: "component", x: 600, y: 20, w: 140, h: 100, titulo: "shared-resources", linhas: ["Auth e catálogo", "Flask, GraphQL, Redis"] },
    { id: "mq", forma: "caixa", estereotipo: "component", x: 600, y: 150, w: 140, h: 90, titulo: "RabbitMQ", linhas: ["limita só a rota", "/campus (consolidada)"] },
    { id: "db", forma: "caixa", estereotipo: "component", x: 330, y: 230, w: 190, h: 90, titulo: "MongoDB", linhas: ["campus, salas, ofertas", "eventos e reservas"] },
    { id: "pdf", forma: "caixa", estereotipo: "component", x: 600, y: 270, w: 140, h: 90, titulo: "Typst + MinIO", linhas: ["PDF do pedido", "guardado no bucket"] },
    { id: "mail", forma: "caixa", estereotipo: "component", x: 20, y: 230, w: 270, h: 100, titulo: "Envio de e-mail", linhas: ["externo: Cloud Function da DW", "local: simulador (compose.yaml:79)"] },
  ],
  ligacoes: [
    { de: "spa", para: "api", rotulo: "HTTP/JSON", tracejada: true },
    { de: "api", para: "cat", rotulo: "GraphQL, evidência parcial", tracejada: true },
    { de: "cat", para: "mq", rotulo: "/campus", tracejada: true },
    { de: "api", para: "db", rotulo: "pymongo", tracejada: true },
    { de: "api", para: "pdf", rotulo: "typst, minio", tracejada: true },
    { de: "api", para: "mail", rotulo: "POST /send-email", tracejada: true },
  ],
  alternativa: "A SPA chama a API Reservas por HTTP (a demonstração só consulta GET /rooms, por ID). A API usa o MongoDB (pymongo), gera o PDF com Typst e o guarda no MinIO, e pede o envio do e-mail por HTTP: a Cloud Function da DW no ambiente real, o simulador local no dev-local. A ligação com shared-resources tem evidência parcial: python-services/src/SLL/cluster_api/request_methods.py:76 e :90 fazem POST GraphQL em URL_graph, sem que eu tenha mapeado cada rota até o catálogo. O RabbitMQ só aparece como limitador da rota /campus (shared-resources/internal_apis/src/SLL/campus_routes.py:12-13, branch consolidada), não de todo o catálogo. O motor roda dentro da SPA.",
};

export const CLASSES = {
  id: "uml-classes",
  titulo: "Modelo conceitual do motor de regras",
  legenda: "Modelo conceitual dos objetos de motor.js (não são classes declaradas). Campos de Sala.fatos: campus, predio, andar, capacidade, recursos. Fato ausente leva a 'indeterminada'.",
  largura: 760,
  altura: 340,
  elementos: [
    { id: "sala", forma: "caixa", x: 20, y: 20, w: 220, h: 110, titulo: "Sala", atributos: ["id", "rotulo", "fatos[campo]: Fato"], operacoes: [] },
    { id: "fato", forma: "caixa", x: 20, y: 200, w: 220, h: 110, titulo: "Fato", atributos: ["valor", "fonte", "confirmadoEm"], operacoes: [] },
    { id: "regra", forma: "caixa", x: 290, y: 20, w: 230, h: 170, titulo: "Regra", atributos: ["id", "descricao", "fonte", "validadaPor"], operacoes: ["aplica(pedido)", "avalia(sala, pedido)"] },
    { id: "ped", forma: "caixa", x: 290, y: 220, w: 230, h: 110, titulo: "Pedido", atributos: ["participantes", "recursos[]", "campus"], operacoes: [] },
    { id: "res", forma: "caixa", x: 560, y: 20, w: 190, h: 140, titulo: "Resultado", atributos: ["recomendadas", "indeterminadas", "rejeitadas", "semCriterio", "regrasNaoValidadas"], operacoes: [] },
    { id: "loc", forma: "caixa", x: 560, y: 200, w: 190, h: 110, titulo: "Localizacao", atributos: ["conhecidos", "ausentes", "trajeto = null"], operacoes: [] },
  ],
  ligacoes: [
    { de: "sala", para: "fato", multiplicidadePara: "0..*", semSeta: true },
    { de: "regra", para: "sala", rotulo: "avalia", tracejada: true },
    { de: "regra", para: "ped", rotulo: "usa", tracejada: true },
    { de: "sala", para: "loc", rotulo: "deriva", tracejada: true },
  ],
  alternativa: "Modelo conceitual: uma Sala tem zero ou mais Fatos (em motor.js, sala.fatos é um objeto indexado por campo), cada um com valor e fonte. Uma Regra avalia uma Sala segundo um Pedido; recomendar reúne as avaliações no Resultado, separado em recomendadas, indeterminadas e rejeitadas. Localizacao é derivada da Sala e nunca tem trajeto.",
};

export const ATIVIDADES = {
  id: "uml-atividades",
  titulo: "Atividades de recomendar()",
  legenda: "Fluxo de recomendar em motor.js. Fato ausente nunca vira 'atende'; sem regra aplicável nada é recomendado.",
  largura: 760,
  altura: 490,
  elementos: [
    { id: "ini", forma: "inicio", x: 22, y: 36, w: 18, h: 18 },
    { id: "a1", forma: "acao", x: 60, y: 20, w: 140, h: 50, rotulo: "Receber pedido\ne salas" },
    { id: "a2", forma: "acao", x: 225, y: 20, w: 150, h: 50, rotulo: "Selecionar regras\naplicáveis" },
    { id: "d1", forma: "decisao", x: 400, y: 8, w: 150, h: 74, rotulo: "Há regra\naplicável?" },
    { id: "a3", forma: "acao", x: 585, y: 15, w: 160, h: 60, rotulo: "Listas vazias e\nsemCriterio = true" },
    { id: "fim2", forma: "fim", x: 666, y: 98, w: 22, h: 22 },
    { id: "reg", forma: "regiao", x: 20, y: 140, w: 720, h: 225, rotulo: "para cada sala (iteração)" },
    { id: "d2", forma: "decisao", x: 40, y: 165, w: 190, h: 80, rotulo: "Alguma regra\nnão atende?" },
    { id: "d3", forma: "decisao", x: 290, y: 165, w: 190, h: 80, rotulo: "Algum fato\nausente?" },
    { id: "r3", forma: "acao", x: 540, y: 185, w: 170, h: 40, rotulo: "Sala recomendada" },
    { id: "r1", forma: "acao", x: 45, y: 290, w: 180, h: 40, rotulo: "Sala rejeitada" },
    { id: "r2", forma: "acao", x: 295, y: 290, w: 180, h: 40, rotulo: "Sala indeterminada" },
    { id: "a4", forma: "acao", x: 230, y: 395, w: 300, h: 44, rotulo: "Devolver listas por status,\nregrasNaoValidadas e semCriterio" },
    { id: "fim", forma: "fim", x: 369, y: 457, w: 22, h: 22 },
  ],
  ligacoes: [
    { de: "ini", para: "a1" },
    { de: "a1", para: "a2" },
    { de: "a2", para: "d1" },
    { de: "d1", para: "a3", rotulo: "[não]" },
    { de: "a3", para: "fim2" },
    { de: "d1", para: "d2", rotulo: "[sim]" },
    { de: "d2", para: "r1", rotulo: "[sim]" },
    { de: "d2", para: "d3", rotulo: "[não]" },
    { de: "d3", para: "r2", rotulo: "[sim]" },
    { de: "d3", para: "r3", rotulo: "[não]" },
    { de: "r1", para: "a4" },
    { de: "r2", para: "a4" },
    { de: "r3", para: "a4" },
    { de: "a4", para: "fim" },
  ],
  alternativa: "Dado um pedido e as salas, o motor seleciona as regras aplicáveis. Se não houver nenhuma, devolve listas vazias e semCriterio = true, e termina. Senão, para cada sala: se alguma regra não atende, a sala é rejeitada; se nenhuma rejeita mas algum fato falta, é indeterminada; só com todas atendidas é recomendada. Ao fim, devolve as listas por status, as regras ainda não validadas (regrasNaoValidadas) e semCriterio = false.",
};

export const SEQUENCIA = {
  id: "uml-sequencia",
  titulo: "Sequência da recomendação",
  legenda: "Fluxo do protótipo; a consulta ao catálogo é opcional, exige o ID e envia o Bearer guardado no navegador, se houver (reservas/src/services/client.js:77-82). Tracejado com ponta aberta: retorno.",
  participantes: ["Solicitante", "SPA", "Motor de regras", "API Reservas"],
  mensagens: [
    { de: 0, para: 1, texto: "informa participantes, recursos, campus" },
    { de: 1, para: 3, texto: "opcional: GET /rooms?roomId=…" },
    { de: 3, para: 1, texto: "uma sala do catálogo", tracejada: true },
    { de: 1, para: 2, texto: "recomendar(salas, pedido)" },
    { de: 2, para: 1, texto: "recomendadas, indeterminadas, rejeitadas", tracejada: true },
    { de: 1, para: 0, texto: "lista com regra, fato e fonte", tracejada: true },
  ],
  alternativa: "O Solicitante informa o evento. A SPA usa salas sintéticas ou consulta opcionalmente uma sala por ID na API; entrega os dados ao motor e mostra as justificativas. A demonstração não realiza reserva.",
};

export const NOTA_TECNOLOGIAS = "Arquivo:linha conferidos nas branches consolidate/2026-10-19 (python-services 8ded63b, shared-resources 1707c8e), em dev-local/compose.yaml e nesta branch; versões são as faixas declaradas, não as resolvidas nos lockfiles. Em outro SHA as linhas podem mudar.";

export const TECNOLOGIAS = [
  { camada: "Interface", itens: "JavaScript (ESM), React 19, React Router 8 em modo SPA sem SSR, Vite 8, Sass, Bootstrap 5", onde: "interfaces-usuario: reservas/package.json:5 (type module), :13 (react), :18 (react-router), :19 (sass), :10 (bootstrap), :29 (vite); reservas/react-router.config.js:3 (ssr: false)" },
  { camada: "API e serviços", itens: "Python 3.12+, Flask, Gunicorn, pymongo; Auth e catálogo com Flask, GraphQL (graphene) e MongoEngine", onde: "python-services/pyproject.toml:17 (python), :19 (flask), :24 (pymongo), :29 (gunicorn); shared-resources/internal_apis/pyproject.toml:21 (graphene), :29 (mongoengine)" },
  { camada: "Dados", itens: "MongoDB 8 para catálogo, eventos e reservas; Redis para cache; MinIO para os PDFs; RabbitMQ só para o limitador da rota /campus do catálogo", onde: "dev-local/compose.yaml:30 (mongo:8.0), :41 (redis), :57 (minio), :159 (rabbitmq); shared-resources/internal_apis/pyproject.toml:34 (redis), :37 (pika); internal_apis/src/SLL/campus_routes.py:12-13 (limitador)" },
  { camada: "Documentos e e-mail", itens: "Typst gera o PDF do pedido e o MinIO o guarda; o e-mail de aprovação é enviado por HTTP à Cloud Function da DW, ou ao simulador local no dev-local", onde: "python-services/src/BLL/pdf.py:5-6 (typst, minio), :325 (typst.compile), :356 (fput_object); python-services/src/SLL/email_service.py:73 (URL), :78 (requests.post); dev-local/compose.yaml:79 (simulador), :112 (CLOUD_FUNCTION_URL)" },
  { camada: "Testes", itens: "node:test na interface e pytest nos serviços Python", onde: "interfaces-usuario: reservas/package.json:24 (node --test); python-services/pyproject.toml:32 (pytest); shared-resources/internal_apis/pyproject.toml:25 (pytest)" },
  { camada: "Execução e entrega", itens: "Docker e Docker Compose em Linux; código no GitHub; staging estático no Render", onde: "dev-local/compose.yaml:30 (imagens); interfaces-usuario: ops/staging.Dockerfile:1 (node) e :10 (yarn build); ops/staging-release.py:26 (URL do Render, só endereço: não prova entrega)" },
  { camada: "Ferramentas", itens: "IDE: a preencher pelo Lucas; controle de versão: Git", onde: "A preencher pelo Lucas (a IDE não está registrada em nenhum repositório)" },
];
