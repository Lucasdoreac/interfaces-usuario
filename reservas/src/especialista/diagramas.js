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
    { id: "ass", forma: "ator", x: 690, y: 200, rotulo: "Assessoria Acadêmica" },
    { id: "u1", forma: "elipse", x: 140, y: 55, w: 320, h: 44, rotulo: "Informar o pedido (participantes, datas, turnos)" },
    { id: "u2", forma: "elipse", x: 140, y: 115, w: 320, h: 44, rotulo: "Receber a triagem com justificativa" },
    { id: "u3", forma: "elipse", x: 140, y: 175, w: 320, h: 44, rotulo: "Consultar sala real por ID (campus e o que falta)" },
    { id: "u5", forma: "elipse", x: 140, y: 235, w: 320, h: 44, rotulo: "Validar as regras do procedimento", tracejado: true },
    { id: "u4", forma: "elipse", x: 140, y: 335, w: 320, h: 44, rotulo: "Pedir reserva (fluxo atual, fora do protótipo)" },
  ],
  ligacoes: [
    { de: "sol", para: "u1" }, { de: "sol", para: "u2" }, { de: "sol", para: "u3" }, { de: "sol", para: "u4" },
    { de: "ass", para: "u4" }, { de: "ass", para: "u5" },
  ],
  alternativa: "Dentro do protótipo, o Solicitante informa o pedido (participantes, datas e turnos), recebe a triagem contra o procedimento da Assessoria com a justificativa de cada regra, e pode consultar uma sala real por ID, vendo o campus e o que falta. A validação das regras pela Assessoria ainda não está implementada. Fora do protótipo fica o pedido de reserva, que já existe no sistema de Reservas, com a Assessoria Acadêmica. A demonstração não faz reserva.",
};

export const COMPONENTES = {
  id: "uml-componentes",
  titulo: "Componentes",
  legenda: "Setas tracejadas: dependência (quem usa quem). Nem toda ligação tem a mesma evidência: veja o texto.",
  largura: 760,
  altura: 380,
  elementos: [
    { id: "spa", forma: "caixa", estereotipo: "component", x: 20, y: 20, w: 250, h: 150, titulo: "SPA Reservas", linhas: ["React 19 + React Router 8", "páginas e formulário de evento", "especialista/triagem.js (puro)", "especialista/catalogo.js"] },
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
  alternativa: "A SPA chama a API Reservas por HTTP (a demonstração só consulta GET /rooms, por ID, e só se o usuário pedir). A API usa o MongoDB (pymongo), gera o PDF com Typst e o guarda no MinIO, e pede o envio do e-mail por HTTP: a Cloud Function da DW no ambiente real, o simulador local no dev-local. A ligação com shared-resources tem evidência parcial: python-services/src/SLL/cluster_api/request_methods.py:76 e :90 fazem POST GraphQL em URL_graph, sem que eu tenha mapeado cada rota até o catálogo. O RabbitMQ só aparece como limitador da rota /campus (shared-resources/internal_apis/src/SLL/campus_routes.py:12-13, branch consolidada), não de todo o catálogo. A triagem roda dentro da SPA e não grava nada.",
};

export const CLASSES = {
  id: "uml-classes",
  titulo: "Modelo conceitual da triagem",
  legenda: "Modelo conceitual dos objetos de triagem.js e motor.js (não são classes declaradas). Localizacao é derivada de uma sala do catálogo (id, rotulo, fatos). Fato não derivado leva a 'indeterminada'.",
  largura: 760,
  altura: 460,
  elementos: [
    { id: "ped", forma: "caixa", x: 20, y: 20, w: 200, h: 110, titulo: "Pedido", atributos: ["participantes", "linhas[]", "excecao"], operacoes: [] },
    { id: "lin", forma: "caixa", x: 20, y: 200, w: 200, h: 100, titulo: "Linha", atributos: ["data", "turno"], operacoes: [] },
    { id: "fato", forma: "caixa", x: 280, y: 20, w: 200, h: 110, titulo: "Fato", atributos: ["valor", "fonte", "derivadoDe"], operacoes: [] },
    { id: "der", forma: "caixa", x: 280, y: 190, w: 200, h: 150, titulo: "Derivacao", atributos: ["id", "produz", "depende[]"], operacoes: ["quando(fatos)", "calcula(fatos)"] },
    { id: "regra", forma: "caixa", x: 540, y: 20, w: 200, h: 150, titulo: "Regra", atributos: ["id", "descricao", "fonte", "validadaPor"], operacoes: ["avalia(fatos)"] },
    { id: "res", forma: "caixa", x: 540, y: 220, w: 200, h: 140, titulo: "Resultado", atributos: ["conclusao", "justificativas", "cadeia", "avisos", "regrasNaoValidadas"], operacoes: [] },
    { id: "loc", forma: "caixa", x: 20, y: 340, w: 200, h: 110, titulo: "Localizacao", atributos: ["conhecidos", "ausentes", "trajeto = null"], operacoes: [] },
  ],
  ligacoes: [
    { de: "ped", para: "lin", multiplicidadePara: "0..*", semSeta: true },
    { de: "ped", para: "fato", rotulo: "gera fatos base", tracejada: true },
    { de: "der", para: "fato", rotulo: "produz", tracejada: true },
    { de: "regra", para: "fato", rotulo: "usa", tracejada: true },
    { de: "res", para: "regra", rotulo: "reúne", tracejada: true },
  ],
  alternativa: "Modelo conceitual: um Pedido tem zero ou mais Linhas (data e turno) e gera Fatos base. Derivações produzem novos Fatos a partir de outros, até não haver mais o que derivar. Cada Regra avalia os Fatos e o Resultado reúne as avaliações com a conclusão, a cadeia de derivações e as regras ainda não validadas. Localizacao, derivada de uma sala do catálogo, mostra o que se sabe e o que falta, e nunca tem trajeto.",
};

export const ATIVIDADES = {
  id: "uml-atividades",
  titulo: "Atividades de triar()",
  legenda: "Fluxo de triar em triagem.js. Fato que não pôde ser derivado nunca vira 'atende'; exceção declarada vai à Assessoria.",
  largura: 760,
  altura: 520,
  elementos: [
    { id: "ini", forma: "inicio", x: 22, y: 36, w: 18, h: 18 },
    { id: "a1", forma: "acao", x: 60, y: 20, w: 130, h: 50, rotulo: "Receber\no pedido" },
    { id: "a2", forma: "acao", x: 215, y: 20, w: 150, h: 50, rotulo: "Montar os\nfatos base" },
    { id: "a3", forma: "acao", x: 390, y: 20, w: 170, h: 50, rotulo: "Encadear: derivar\naté não haver mais" },
    { id: "reg", forma: "regiao", x: 585, y: 4, w: 160, h: 84, rotulo: "para cada regra" },
    { id: "a4", forma: "acao", x: 595, y: 28, w: 140, h: 50, rotulo: "Avaliar nos\nfatos" },
    { id: "d1", forma: "decisao", x: 40, y: 120, w: 170, h: 80, rotulo: "Exceção\ndeclarada?" },
    { id: "r1", forma: "acao", x: 260, y: 140, w: 170, h: 40, rotulo: "Concluir: assessoria" },
    { id: "d2", forma: "decisao", x: 40, y: 240, w: 170, h: 80, rotulo: "Alguma regra\nnão atende?" },
    { id: "r2", forma: "acao", x: 260, y: 260, w: 170, h: 40, rotulo: "Concluir: viola" },
    { id: "d3", forma: "decisao", x: 40, y: 350, w: 170, h: 80, rotulo: "Alguma regra\nindeterminada?" },
    { id: "r3", forma: "acao", x: 260, y: 370, w: 170, h: 40, rotulo: "Concluir: incompleto" },
    { id: "r4", forma: "acao", x: 45, y: 455, w: 160, h: 40, rotulo: "Concluir: dentro" },
    { id: "a5", forma: "acao", x: 500, y: 300, w: 240, h: 60, rotulo: "Devolver conclusão, justificativas,\ncadeia e regrasNaoValidadas" },
    { id: "fim", forma: "fim", x: 609, y: 400, w: 22, h: 22 },
  ],
  ligacoes: [
    { de: "ini", para: "a1" },
    { de: "a1", para: "a2" },
    { de: "a2", para: "a3" },
    { de: "a3", para: "a4" },
    { de: "a4", para: "d1" },
    { de: "d1", para: "r1", rotulo: "[sim]" },
    { de: "d1", para: "d2", rotulo: "[não]" },
    { de: "d2", para: "r2", rotulo: "[sim]" },
    { de: "d2", para: "d3", rotulo: "[não]" },
    { de: "d3", para: "r3", rotulo: "[sim]" },
    { de: "d3", para: "r4", rotulo: "[não]" },
    { de: "r1", para: "a5" },
    { de: "r2", para: "a5" },
    { de: "r3", para: "a5" },
    { de: "r4", para: "a5" },
    { de: "a5", para: "fim" },
  ],
  alternativa: "Dado um pedido, a triagem monta os fatos base (participantes, linhas, exceção) e encadeia: deriva novos fatos, por exemplo as reservas de cada dia e se o limite foi respeitado, até não haver mais o que derivar. Depois avalia cada regra sobre os fatos. Se há exceção declarada, a conclusão é 'assessoria'; senão, se alguma regra não atende, é 'viola'; senão, se alguma ficou indeterminada, é 'incompleto'; só com todas atendidas é 'dentro'. O resultado traz também a cadeia de derivações e as regras ainda não validadas.",
};

export const SEQUENCIA = {
  id: "uml-sequencia",
  titulo: "Sequência da triagem",
  legenda: "Fluxo do protótipo; a consulta ao catálogo é opcional, exige o ID e envia o Bearer guardado no navegador, se houver (reservas/src/services/client.js:77-82). Tracejado com ponta aberta: retorno.",
  participantes: ["Usuário", "SPA", "Triagem", "API Reservas"],
  mensagens: [
    { de: 0, para: 1, texto: "digita participantes, datas e turnos" },
    { de: 1, para: 2, texto: "triar(pedido)" },
    { de: 2, para: 1, texto: "conclusão, justificativas, cadeia", tracejada: true },
    { de: 1, para: 0, texto: "mostra regra, fatos e fonte", tracejada: true },
    { de: 0, para: 1, texto: "opcional: informa o ID de uma sala" },
    { de: 1, para: 3, texto: "GET /rooms?roomId=…" },
    { de: 3, para: 1, texto: "rótulo e campus", tracejada: true },
    { de: 1, para: 0, texto: "campus e o que falta", tracejada: true },
  ],
  alternativa: "O Usuário digita o pedido; a SPA chama a triagem, que devolve a conclusão com as justificativas e a cadeia de fatos, e mostra tudo. Opcionalmente o Usuário informa o ID de uma sala, e a SPA consulta a API; a demonstração mostra o campus e o que falta. A demonstração não realiza reserva.",
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
