import React, { useState, useEffect } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate, useLocation } from "react-router-dom";
import InputMask from "react-input-mask";
import { useFormContext } from "../../context/FormContext";
import TwoButtons from "../../components/TwoButtons";
import "./EventBasicInfo.scss";

const EventBasicInfo = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const query = new URLSearchParams(location.search);
  const eventIdFromQuery = query.get("eventId"); // extract eventId from URL

  const {
    formData,
    handleChange,
    saveDraft,
    handleOdsChange,
    fillOutFormData,
    eventTypes,
    odsTypes,
    loading,
    setLoading,
  } = useFormContext();

  const [erros, setErros] = useState({});

  // On mount, fill the form with event data if editing or clear for new event
  useEffect(() => {
    fillOutFormData(eventIdFromQuery || "");
  }, [eventIdFromQuery, fillOutFormData]);

  const validateForm = () => {
    const newErrors = {};
    if (!formData.tituloEvento?.trim()) {
      newErrors.tituloEvento = "O campo nome do evento é obrigatório.";
    } else if (formData.tituloEvento.length < 5) {
      newErrors.tituloEvento =
        "O campo nome do evento precisa ter mais caracteres!";
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

  const handleNext = async () => {
    if (validateForm()) {
      setLoading(true);
      const eventId = await saveDraft();
      setLoading(false);
      if (eventIdFromQuery || eventId) {
        navigate(`/event/details?eventId=${eventIdFromQuery || eventId}`);
      }
    }
  };

  const renderError = (field) =>
    erros[field] && <span style={{ color: "red" }}>{erros[field]}</span>;

  return (
    <form onSubmit={(e) => e.preventDefault()}>
      <div>
        <div className="card-header">
          <div className="d-flex justify-content-start">
            <span
              onClick={() =>
                navigate(`/event/type-selection?eventId=${eventIdFromQuery}`)
              }
            >
              <AiOutlineLeft
                style={{ margin: "0 10px 0 0" }}
                size="20px"
                color="white"
              />
            </span>
          </div>
        </div>

        <div className="card-body">
          <div className="row">
            <div className="col-md-12">
              <h4>{eventIdFromQuery ? "Editar Evento" : "Novo Evento"}</h4>
            </div>
          </div>

          {/* Nome do Evento */}
          <div className="row">
            <div className="col">
              <label htmlFor="formTitulo">Nome do Evento</label>
              <input
                type="text"
                className="form-control"
                id="formTitulo"
                name="tituloEvento"
                value={formData.tituloEvento || ""}
                onChange={handleChange}
                disabled={loading}
              />
              {renderError("tituloEvento")}
            </div>
          </div>

          {/* Professor */}
          <div className="row mt-3">
            <div className="col">
              <label htmlFor="formProfessor">Professor</label>
              <input
                type="text"
                disabled={true}
                className="form-control"
                id="formProfessor"
                name="nomeProfessor"
                value={localStorage.getItem("userEmail") || ""}
                onChange={() => {}}
              />
              {renderError("nomeProfessor")}
            </div>
          </div>

          {/* Telefone */}
          <div className="row mt-3">
            <div className="col">
              <label htmlFor="telefone">Telefone</label>
              <InputMask
                mask="(99) 9 9999-9999"
                id="telefone"
                name="telefone"
                placeholder="(XX) X XXXX-XXXX"
                value={formData.telefone || ""}
                onChange={handleChange}
                disabled={loading}
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
          </div>

          {/* ODS */}
          <div className="row mt-3">
            <div className="col-md-12">
              <label htmlFor="ods">Classificação ODS</label>
              <select
                id="ods"
                name="ods"
                className="form-control"
                value={formData.ods || ""}
                onChange={handleOdsChange}
                disabled={loading}
              >
                <option value="" disabled>
                  ODS
                </option>
                {odsTypes.map((ods, index) => (
                  <option value={ods.id} key={index}>
                    {ods.formatted}
                  </option>
                ))}
              </select>
              {renderError("ods")}
            </div>
          </div>

          {!loading && (
            <TwoButtons saveDraft={saveDraft} handleNext={handleNext} />
          )}
        </div>
      </div>
    </form>
  );
};

export default EventBasicInfo;
