import React, { useState, useEffect } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate, useLocation } from "react-router-dom";
import { useFormContext } from "../../context/FormContext";
import TwoButtons from "../../components/TwoButtons";
import "./EventTypeSelection.scss";
import { ThemeContext } from "../../context/ThemeContext";
import { useContext } from "react";



const EventTypeSelection = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const query = new URLSearchParams(location.search);
  const eventIdFromQuery = query.get("eventId"); // extract eventId from URL
  const { theme } = useContext(ThemeContext)
  
  const {
    formData,
    handleChange,
    saveDraft,
    fillOutFormData,
    eventTypes,
    loading,
    setLoading,
  } = useFormContext();
  
  const [erros, setErros] = useState({});
  useEffect(() => {
    if (theme == "dark"){
      document.body.classList.add("dark-theme")
    }
    else {
      document.body.classList.remove("dark-theme")
    }
  }, [theme]);
  
  // On mount, fill the form with event data if editing or clear for new event
  useEffect(() => {
    fillOutFormData(eventIdFromQuery || "");
  }, [eventIdFromQuery, fillOutFormData]);
  
  const validateForm = () => {
    const newErrors = {};
    if (!formData.classificacao?.trim()) {
      newErrors.classificacao = "Selecione uma classificação de evento.";
    }
    setErros(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = async () => {
    if (validateForm()) {
      setLoading(true);
      const eventId = await saveDraft();
      setLoading(false);

      if (!eventId) {
        // Inform the user if the draft was not created
        setErros({
          draft: "Não foi possível salvar o rascunho. Tente novamente.",
        });
        return;
      }

      if (eventIdFromQuery || eventId) {
        const selectedEventType = formData.classificacao;

        if (selectedEventType === "class" || selectedEventType === "exam") {
          navigate(`/event/schedule?eventId=${eventIdFromQuery || eventId}`);
        } else {
          navigate(`/event/basic-info?eventId=${eventIdFromQuery || eventId}`);
        }
      }
    }
  };

  const handleRadioChange = (e) => {
    const { name, value } = e.target;
    // Usando o mesmo método handleChange do contexto do formulário
    handleChange({ target: { name, value } });
  };

  const renderError = (field) =>
    erros[field] && <span className="error-message">{erros[field]}</span>;

  return (
    <form onSubmit={(e) => e.preventDefault()}>
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
          </div>
        </div>

        <div className="card-body">
          <div className="row">
            <div className="col-md-12">
              <h4>
                {eventIdFromQuery
                  ? "Editar Tipo de Evento"
                  : "Selecione o Tipo de Evento"}
              </h4>
            </div>
          </div>

          {/* Classificação com Radio Buttons */}
          <div className="classification-container">
            <h5>Classificação do Evento</h5>
            <div className="radio-group">
              {eventTypes.map((eventType, index) => (
                <div className="radio-option" key={index}>
                  <input
                    type="radio"
                    id={`eventType-${eventType.type}`}
                    name="classificacao"
                    value={eventType.type}
                    checked={formData.classificacao === eventType.type}
                    onChange={handleRadioChange}
                    disabled={loading}
                  />
                  <label
                    htmlFor={`eventType-${eventType.type}`}
                    className={
                      formData.classificacao === eventType.type
                        ? "selected"
                        : ""
                    }
                  >
                    {eventType.name}
                  </label>
                </div>
              ))}
            </div>
            {renderError("classificacao")}
          </div>

          {!loading && (
            <div className="buttons-container">
              {erros.draft && (
                <span className="error-message">{erros.draft}</span>
              )}
              <TwoButtons saveDraft={saveDraft} handleNext={handleNext} />
            </div>
          )}
        </div>
      </div>
    </form>
  );
};

export default EventTypeSelection;
