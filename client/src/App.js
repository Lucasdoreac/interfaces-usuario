import React from 'react';
import './App.scss';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './pages/Home/Home';
import Organizador from './pages/organizador/organizador';
import Navbar from './components/Navbar/Navbar';
import ConfirmarEmail from './pages/confirmar-email/ConfirmarEmail';
import DadosPessoais from './pages/dados-pessoais/DadosPessoais';
import DescricaoEvento from './pages/descricao-evento/DescricaoEvento';
import LocalEvento from './pages/local-evento/LocalEvento';

function App() {
  return (
      <BrowserRouter> {}
        <div className="App">
          <Navbar /> {}
          <section id="paginaInicial" className="section-padding">
            <div className="container">
              <div className="row justify-content-center">
                <div className="col-md-6">
                  <div className="card">
                    <Routes>
                      <Route path="/" element={<Home />} />
                      <Route path="/organizador" element={<Organizador />} />
                      <Route path="/confirmar-email" element={<ConfirmarEmail />} />
                      <Route path="/dados-pessoais" element={<DadosPessoais />} />
                      <Route path="/descricao-evento" element={<DescricaoEvento />} />
                      <Route path="/local-evento" element={<LocalEvento />} />
                    </Routes>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </BrowserRouter>
  );
}

export default App;
