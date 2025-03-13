import React from "react";
import "./App.scss";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home/Home";
import Organizador from "./pages/organizador/organizador";
import EmailCoordination from "./pages/approve-event";
import Navbar from "./components/Navbar/Navbar";
import ConfirmarEmail from "./pages/confirmar-email/ConfirmarEmail";
import DadosPessoais from "./pages/dados-pessoais/DadosPessoais";
import DescricaoEvento from "./pages/descricao-evento/DescricaoEvento";
import LocalEvento from "./pages/local-evento/LocalEvento";
import AcessoNegado from "./pages/acesso-negado/AcessoNegado";
import PrivateRoute from "./PrivateRoute";
import { FormProvider } from "./context/FormContext";
import EventoConfirmacao from "./pages/evento-confirmacao/EventoConfirmacao";
import MeusEventos from "./pages/meus-eventos/MeusEventos";

function App() {
  return (
    <FormProvider>
      <BrowserRouter>
        <div className="App">
          <Navbar />
          <section id="paginaInicial" className="section-padding">
            <div>
              <div className="row justify-content-center">
                <div className="col-md-12 col-sm-12 col-12">
                  <div className="card">
                    <Routes>
                      <Route path="/" element={<Home />} />
                      <Route path="/organizador" element={<Organizador />} />
                      <Route
                        path="/auth/callback"
                        element={<ConfirmarEmail />}
                      />
                      <Route
                        path="/coordenacao"
                        element={<EmailCoordination />}
                      />
                      <Route
                        path="/dados-pessoais"
                        element={<PrivateRoute element={DadosPessoais} />}
                      />
                      <Route
                        path="/descricao-evento"
                        element={<PrivateRoute element={DescricaoEvento} />}
                      />
                      <Route
                        path="/local-evento"
                        element={<PrivateRoute element={LocalEvento} />}
                      />
                      <Route
                        path="/evento-confirmacao"
                        element={<PrivateRoute element={EventoConfirmacao} />}
                      />
                      <Route
                        path="/meus-eventos"
                        element={<PrivateRoute element={MeusEventos} />}
                      />
                      <Route path="/acesso-negado" element={<AcessoNegado />} />
                    </Routes>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </BrowserRouter>
    </FormProvider>
  );
}

export default App;
