import React from "react";
import { useNavigate } from "react-router-dom";
import EnvImage from "../../images/schedule.png";

const EventConfirmation = () => {
  const navigate = useNavigate();

  const handleViewEvents = () => {
    navigate("/event/mine"); // Rota para a página onde o usuário pode acompanhar o status dos eventos
  };

  return (
    <div className="evento-confirmacao-container">
      <div className="card-body">
        <div className="row">
          <div className="col-md-12 text-center">
            <img
              src={EnvImage}
              style={{ width: "200px" }}
              alt="Confirmação de Envio"
              className="confirmacao-imagem"
            />
            <h2>Evento Enviado com Sucesso!</h2>
            <p>
              Seu evento foi enviado para análise. Você pode acompanhar a
              situação de seus eventos na aba "Meus Eventos".
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleViewEvents}
            >
              Ver Meus Eventos
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EventConfirmation;
