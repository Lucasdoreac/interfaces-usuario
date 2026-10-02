import {
  isRouteErrorResponse,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from "react-router";
import "../src/index.scss";
import "../src/App.scss";
import Navbar from "../src/components/Navbar/Navbar";
// Bootstrap last, as in the previous CRA entry (src/index.js): the app's own
// rules (.nav, .card, .btn…) are written against that order, and loading
// Bootstrap first lets the app CSS win ties it used to lose.
import "bootstrap/dist/css/bootstrap.min.css";

export function meta() {
  return [
    { title: "Reservas UDF | LabTech" },
    {
      name: "description",
      content: "Sistema de reserva de espaços do Centro Universitário UDF.",
    },
  ];
}

export function Layout({ children }) {
  return (
    <html lang="pt-BR">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function Root() {
  return (
    <div className="App">
      <Navbar />
      <section id="paginaInicial" className="section-padding">
        <div>
          <div className="row justify-content-center">
            <div className="col-md-12 col-sm-12 col-12">
              <main className="card">
                <Outlet />
              </main>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export function ErrorBoundary({ error }) {
  const isRouteError = isRouteErrorResponse(error);
  const message = isRouteError
    ? `${error.status} ${error.statusText}`
    : "Erro inesperado";

  return (
    <main className="container py-5" role="alert">
      <h1>Não foi possível carregar esta página</h1>
      <p>{message}</p>
      {import.meta.env.DEV && error instanceof Error && <pre>{error.stack}</pre>}
    </main>
  );
}
