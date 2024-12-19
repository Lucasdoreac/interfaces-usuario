import React, { useState, useEffect } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import "./DadosPessoais.scss";
import { useNavigate } from "react-router-dom";
import InputMask from "react-input-mask";
import { useFormContext } from "../../context/FormContext";
import apiService from "../../services/client";
import TwoButtons from "../../components/TwoButtons";

const DadosPessoais = () => {
  const navigate = useNavigate();
  const { formData, handleChange, handleSaveDraft } = useFormContext();

  const [listaTipoEvento, setListaTipoEvento] = useState([]);
  const [listaODS, setListaODS] = useState([]);
  const [erros, setErros] = useState({});

  useEffect(() => {
    const fetchEventData = async () => {
      try {
        const data = await apiService.getTypes();
        if (data?.types) {
          setListaTipoEvento(
            data.types
              .find((item) => item.collection === "events")
              ?.types.map((t) => t.type) || []
          );
          setListaODS(
            data.types
              .find((item) => item.collection === "ODS")
              ?.types.map((ods) => `${ods.name} (${ods.type})`) || []
          );
        }
      } catch (error) {
        console.error("Failed to fetch event data:", error);
      }
    };

    fetchEventData();
  }, []);

  const validateForm = () => {
    const newErrors = {};

    if (!formData.tituloEvento?.trim()) {
      newErrors.tituloEvento = "O campo nome do evento é obrigatório.";
    } else if (formData.tituloEvento.length < 5) {
      newErrors.tituloEvento =
        "O campo nome do evento precisa ter mais caracteres!";
    }

    if (!formData.nomeProfessor?.trim()) {
      newErrors.nomeProfessor = "O campo PROFESSOR é obrigatório.";
    }

    if (!formData.classificacao?.trim()) {
      newErrors.classificacao = "Defina uma classificação.";
    }

    if (!formData.ods?.trim()) {
      newErrors.ods = "Defina uma ODS.";
    }

    setErros(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validateForm()) {
      handleSaveDraft();
      navigate("/descricao-evento");
    }
  };

  const renderError = (field) =>
    erros[field] && <span style={{ color: "red" }}>{erros[field]}</span>;

  return (
    <form>
      <div>
        <div className="card-header">
          <div className="d-flex justify-content-start">
            <span onClick={() => navigate("/auth/callback")}>
              <AiOutlineLeft
                style={{ margin: "0 10px 0 0" }}
                size="20px"
                color="white"
              />
            </span>
            <h5>X Cancelar</h5>
          </div>
        </div>

        <div className="card-body">
          <div className="row">
            <div className="col-md-12">
              <h4>Novo Evento</h4>
            </div>
          </div>

          {/* Form Fields */}
          <div className="row">
            <div className="col">
              <label htmlFor="formTitulo">Nome do Evento</label>
              <input
                type="text"
                className="form-control"
                id="formTitulo"
                name="tituloEvento"
                value={formData.tituloEvento}
                onChange={handleChange}
              />
              {renderError("tituloEvento")}
            </div>
          </div>

          <div className="row mt-3">
            <div className="col">
              <label htmlFor="formProfessor">Professor</label>
              <input
                type="text"
                disabled
                className="form-control"
                id="formProfessor"
                name="nomeProfessor"
                value={formData.nomeProfessor}
              />
              {renderError("nomeProfessor")}
            </div>
          </div>

          <div className="row mt-3">
            <div className="col">
              <label htmlFor="telefone">Telefone</label>
              <InputMask
                mask="(99) 9 9999-9999"
                id="telefone"
                name="telefone"
                placeholder="(XX) XXXXX-XXXX"
                value={formData.telefone || ""}
                onChange={handleChange}
              >
                {(inputProps) => (
                  <input
                    {...inputProps}
                    type="text"
                    className="form-control"
                    style={{ width: 200 }}
                  />
                )}
              </InputMask>
              {renderError("telefone")}
            </div>

            <div className="col">
              <label htmlFor="classificacao">Classificação</label>
              <select
                className="form-control"
                style={{ width: 150 }}
                id="classificacao"
                name="classificacao"
                value={formData.classificacao || ""}
                onChange={handleChange}
              >
                <option value="" disabled>
                  Tipo do Evento
                </option>
                {listaTipoEvento.map((evt, index) => (
                  <option value={evt} key={index}>
                    {evt}
                  </option>
                ))}
              </select>
              {renderError("classificacao")}
            </div>
          </div>

          <div className="row mt-3">
            <div className="col-md-12">
              <label htmlFor="ods">Classificação ODS</label>
              <select
                id="ods"
                name="ods"
                className="form-control"
                value={formData.ods || ""}
                onChange={handleChange}
              >
                <option value="" disabled>
                  ODS
                </option>
                {listaODS.map((ods, index) => (
                  <option value={ods} key={index}>
                    {ods}
                  </option>
                ))}
              </select>
              {renderError("ods")}
            </div>
          </div>

          <TwoButtons
            handleSaveDraft={handleSaveDraft}
            handleNext={handleNext}
          />
        </div>
      </div>
    </form>
  );
};

export default DadosPessoais;
