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
import ThemeToggleButton from "../src/components/Button/ThemeToggleButton";
import { ThemeProvider } from "../src/context/ThemeContext";
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
    <ThemeProvider>
      <div className="App">
        <Navbar />
        <ThemeToggleButton />
        <section id="paginaInicial" className="section-padding">
        <div>
          <div className="row justify-content-center">
            <div className="col-md-12 col-sm-12 col-12">
              <div className="card">
                <Outlet />
              </div>
            </div>
          </div>
        </div>
        </section>
      </div>
    </ThemeProvider>
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
