import React from "react";
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate } from "react-router-dom";
import { useFormContext } from "../../context/FormContext"; // ajuste o caminho conforme necessário

const LocalEvento = () => {
  const navigate = useNavigate();
  const { formData, handleChange } = useFormContext(); // use o contexto

  const confLocalEvento = () => {
    navigate("/proximo-passo"); // Exemplo de navegação
  };

  return (
    <form>
      <div>
        <div className="card-header">
          <div className="d-flex d-flex justify-content-start">
            <span onClick={() => navigate("/descricao-evento")}>
              <AiOutlineLeft
                style={{ margin: "0px 10px 0px 0px" }}
                size="20px"
                color="white"
              />
            </span>
            <h5>Voltar Descrição Evento</h5>
          </div>
        </div>
        <div className="card-body">
          <div className="row">
            <div className="col-md-12">
              <h4>Novo Evento</h4>
            </div>
          </div>
          <div className="row">
            <div className="col">
              <label htmlFor="numeroParticipantes">
                Número de participantes
              </label>
              <input
                type="number"
                className="form-control"
                min="0"
                max="100"
                id="numeroParticipantes"
                style={{ width: 200 }}
                name="numeroParticipantes"
                value={formData.numeroParticipantes || ""}
                onChange={handleChange}
              />
            </div>
          </div>
          <br />
          <div className="row">
            <div className="col">
              <label htmlFor="espacos">Espaços Necessários</label>
              <br />
              {[
                "online",
                "auditorio",
                "hall",
                "salaAula",
                "laboratorioInfo",
              ].map((espaco) => (
                <div className="form-check" key={espaco}>
                  <input
                    className="form-check-input"
                    type="radio"
                    name="espacos"
                    id={espaco}
                    onChange={handleChange}
                    value={espaco}
                    checked={formData.espacos === espaco}
                  />
                  <label className="form-check-label" htmlFor={espaco}>
                    {espaco.charAt(0).toUpperCase() +
                      espaco.slice(1).replace(/([A-Z])/g, " $1")}
                  </label>
                </div>
              ))}
            </div>
          </div>
          <br />
          <div className="row">
            <div className="col-5">
              <label htmlFor="trilha">Trilha empreendedora</label>
              <select
                id="trilha"
                name="trilha"
                value={formData.trilha || ""}
                onChange={handleChange}
                className="form-control"
              >
                <option value="" disabled></option>
                <option value="sim">Sim</option>
                <option value="nao">Não</option>
              </select>
            </div>
            <div className="col-7">
              <label htmlFor="trilhaDesc">Se sim, digite aqui</label>
              <input
                type="text"
                className="form-control"
                id="trilhaDesc"
                name="trilhaDesc"
                value={formData.trilhaDesc || ""}
                onChange={handleChange}
              />
            </div>
          </div>
          <br />
          <div className="row">
            <div className="col-5">
              <label htmlFor="projeto">Projeto Extensão</label>
              <select
                id="projeto"
                name="projeto"
                value={formData.projeto || ""}
                onChange={handleChange}
                className="form-control"
              >
                <option value="" disabled></option>
                <option value="sim">Sim</option>
                <option value="nao">Não</option>
              </select>
            </div>
            <div className="col-7">
              <label htmlFor="projetoDesc">Se sim, digite aqui</label>
              <input
                type="text"
                className="form-control"
                id="projetoDesc"
                name="projetoDesc"
                value={formData.projetoDesc || ""}
                onChange={handleChange}
              />
            </div>
          </div>
          <br />
          <div className="row">
            <div className="col text-center">
              <button
                type="button"
                className="btn btn-primary"
                onClick={confLocalEvento}
              >
                Próximo Passo
              </button>
            </div>
          </div>
        </div>
      </div>
    </form>
  );
};

export default LocalEvento;
