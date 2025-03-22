import React from "react";

const TwoButtons = ({ handleSaveDraft, handleNext }) => {
  return (
    <div className="d-flex mt-3 justify-content-center">
      <div className="d-flex justify-content-between" style={{ width: "50%" }}>
        <button
          type="button"
          className="btn btn-outline-secondary"
          onClick={handleSaveDraft}
        >
          Salvar Rascunho
        </button>
        <button type="button" className="btn btn-primary" onClick={handleNext}>
          Próximo
        </button>
      </div>
    </div>
  );
};

export default TwoButtons;
