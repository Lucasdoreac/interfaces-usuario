import React from "react";
import DraftSaveAlert from "../DraftSaveAlert";

const TwoButtons = ({ handleSaveDraft, handleNext, disabled = false }) => {
  return (
    <div className="mt-3">
      <div className="d-flex justify-content-center">
        <div className="d-flex justify-content-between" style={{ width: "50%" }}>
          <button
            style={{ opacity: 0 }}
            type="button"
            className="btn btn-outline-secondary"
            onClick={handleSaveDraft}
          >
            Salvar Rascunho
          </button>
          <button type="button" className="btn btn-primary" onClick={handleNext} disabled={disabled}>
            {disabled ? "Salvando..." : "Próximo"}
          </button>
        </div>
      </div>
      <DraftSaveAlert />
    </div>
  );
};

export default TwoButtons;
