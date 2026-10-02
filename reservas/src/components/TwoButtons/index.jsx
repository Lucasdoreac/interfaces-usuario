import React from "react";

const TwoButtons = ({ handleSaveDraft, handleNext, disabled = false }) => {
  return (
    <div className="d-flex mt-3 justify-content-center">
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
  );
};

export default TwoButtons;
