import React from "react";
import { Link, useNavigate } from "react-router";
import { useFormContext } from "../../context/FormContext";

// Aviso visível quando o salvamento do rascunho falha. O contêiner role="alert"
// só existe enquanto há falha; no conflito (409) oferece as duas saídas.
const DraftSaveAlert = () => {
  const { saveFailure, fillOutFormData } = useFormContext();
  const navigate = useNavigate();
  if (!saveFailure) return null;

  const startNewEvent = async () => {
    await fillOutFormData("");
    navigate("/event/type-selection");
  };

  return (
    <div role="alert" className="alert alert-warning mt-3 mb-0">
      <p className="mb-2">{saveFailure.message}</p>
      {saveFailure.kind === "conflict" && (
        <div className="d-flex gap-3 align-items-center">
          <Link to="/event/mine">Meus Eventos</Link>
          <button type="button" className="btn btn-link p-0" onClick={startNewEvent}>
            Começar um novo evento
          </button>
        </div>
      )}
    </div>
  );
};

export default DraftSaveAlert;
