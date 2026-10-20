import "./Espacos.scss";
import { Link } from "react-router";

const OFFICIAL_RESERVATION_FORM = "https://forms.cloud.microsoft/r/xHUxLS9yss";
const CURRENT_SPACE_GUIDE = "https://gestaolaboratorios.wixsite.com/agenda";

function Espacos() {
  return (
    <main className="spaces-guide">
      <header className="spaces-guide__hero">
        <p className="spaces-guide__eyebrow">Reservas UDF · LabTech</p>
        <h1>Espaços e orientações</h1>
        <p className="spaces-guide__intro">
          Encontre o caminho certo para solicitar uma sala ou conhecer as regras
          de uso dos espaços da UDF.
        </p>
      </header>

      <section className="spaces-guide__primary" aria-labelledby="classrooms-title">
        <div>
          <p className="spaces-guide__eyebrow">Salas de aula e laboratórios de informática</p>
          <h2 id="classrooms-title">Como solicitar</h2>
          <ol className="spaces-guide__steps">
            <li>Envie o pedido pelo formulário oficial e informe o período desejado.</li>
            <li>Faça a solicitação com pelo menos três dias úteis de antecedência.</li>
            <li>Aguarde a análise e a confirmação formal por e-mail da Assessoria Acadêmica – Planejamento de Ofertas.</li>
          </ol>
          <p className="spaces-guide__note">
            O envio do formulário não confirma a reserva. Pedidos incompletos
            podem levar mais tempo para análise.
          </p>
          <a
            className="btn btn-primary btn-lg"
            href={OFFICIAL_RESERVATION_FORM}
            target="_blank"
            rel="noopener noreferrer"
          >
            Abrir formulário oficial
          </a>
        </div>
      </section>

      <section className="spaces-guide__secondary" aria-labelledby="special-spaces-title">
        <div>
          <p className="spaces-guide__eyebrow">Outros espaços</p>
          <h2 id="special-spaces-title">Laboratórios e ambientes especiais</h2>
          <p>
            Clínicas, Laboratórios 4R, Brinquedoteca, Cozinha Escola e outros
            ambientes podem ter instruções, formulários e requisitos próprios.
            Consulte a orientação vigente para cada espaço antes de solicitar.
          </p>
          <a
            className="spaces-guide__text-link"
            href={CURRENT_SPACE_GUIDE}
            target="_blank"
            rel="noopener noreferrer"
          >
            Consultar guia atual de espaços e laboratórios
          </a>
        </div>
      </section>

      <aside className="spaces-guide__status" aria-label="Status do Staging">
        <h2>Prévia do LabTech</h2>
        <p>
          Esta página organiza as orientações. Nesta etapa, o pedido oficial
          ainda é feito nos formulários indicados; o envio por aqui não cria nem
          confirma uma reserva.
        </p>
      </aside>

      <footer className="spaces-guide__footer">
        <Link to="/organizer">Acesso do organizador</Link>
      </footer>
    </main>
  );
}

export default Espacos;
