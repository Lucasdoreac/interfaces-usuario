import React from "react";
import "./AccessDenied.scss";
import { useNavigate } from "react-router-dom";

const AccessDenied = () => {
  const navigate = useNavigate();

  return (
    <div className="acesso-negado">
      <div className="card-header">
        <div className="row mb-4">
          <div className="col-md-3">{/* Espaço vazio */}</div>
        </div>
      </div>
      <div className="card-body text-center">
        <h1>Acesso Negado</h1>
        <p>Você não tem permissão para acessar esta página.</p>
        <p>Por favor, faça login para continuar.</p>
        <div className="mt-4">
          <button className="btn-voltar" onClick={() => navigate("/")}>
            Voltar para a Página Inicial
          </button>
        </div>
      </div>
    </div>
  );
};

export default AccessDenied;
