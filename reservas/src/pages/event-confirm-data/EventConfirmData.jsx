import React, { useRef, useState } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate, useSearchParams } from "react-router";
import { useFormContext } from "../../context/FormContext";
import apiService from "../../services/client";
import { summarizeEventData } from "../../utils/eventSummary";
import Loading from "../../components/Loading";
import { runSingleFlight } from "../../utils/singleFlight";
import "./EventConfirmData.scss";

const EventConfirmData = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const eventId = searchParams.get("eventId");

  const { formData } = useFormContext();
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const flight = useRef(false);

  const submitEvent = async () => {
    if (!validateForm()) {
      return; // Stop execution if validation fails
    }

    try {
      if (!eventId) {
        setErrors({ api: "Evento não encontrado. Salve o rascunho novamente." });
        return;
      }
      const event_submission = await apiService.submitEventForApproval(
        eventId,
        formData
      );
      if (!event_submission) {
        setErrors({
          api: "Falha ao enviar os dados do evento. Tente novamente mais tarde.",
        });
        return;
      }
      console.log("Form submitted", eventId);
      navigate(`/event/confirmation?eventId=${eventId}`);
    } catch (error) {
      console.error("Error submitting:", error);
      setErrors({
        api: "Ocorreu um erro ao enviar os dados. Tente novamente.",
      });
    }
  };

  const handleConfirm = () => runSingleFlight(flight, submitEvent, setSubmitting);

  const validateForm = () => {
    const newErrors = {};

    if (
      formData.classificacao == "lecture" ||
      formData.classificacao == "workshop"
    ) {
      if (
        !formData.numeroParticipantes?.trim() ||
        formData.numeroParticipantes <= 0
      ) {
        newErrors.numeroParticipantes =
          "Número de participantes é obrigatório.";
      }
      if (!formData.espacos?.trim()) {
        newErrors.espacos = "Selecione um espaço necessário.";
      }
      if (formData.trilha === "sim" && !formData.trilhaDesc?.trim()) {
        newErrors.trilhaDesc =
          "Descrição da trilha empreendedora é obrigatória.";
      }
      if (formData.projeto === "sim" && !formData.projetoDesc?.trim()) {
        newErrors.projetoDesc =
          "Descrição do projeto de extensão é obrigatória.";
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  if (!formData) {
    return <div>Carregando dados...</div>;
  }

  return (
    <div className="confirmar-dados-container">
      <div className="card-header">
        <span onClick={() => navigate(`/event/schedule?eventId=${eventId}`)}>
          <AiOutlineLeft
            size="20px"
            color="white"
            style={{ marginRight: 10 }}
          />
        </span>
      </div>
      <h2>Confirmar Dados do Evento</h2>
      <dl className="dados-preview">
        {summarizeEventData(formData).map(({ label, value }) => (
          <div key={label} className="dados-preview-item">
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {errors.api && (
        <div className="alert alert-danger" role="alert">
          {errors.api}
        </div>
      )}
      <button className="btn btn-primary" onClick={handleConfirm} disabled={submitting}>
        {submitting ? "Enviando..." : "Confirmar"}
      </button>
      {submitting && <Loading />}
    </div>
  );
};

export default EventConfirmData;
