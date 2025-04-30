import React, { useState } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useFormContext } from "../../context/FormContext";
import apiService from "../../services/client";

const EventConfirmData = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const eventId = searchParams.get("eventId");

  const { formData } = useFormContext();
  const [errors, setErrors] = useState({});

  const handleConfirm = async () => {
    if (!validateForm()) {
      return; // Stop execution if validation fails
    }

    try {
      const isReservationSaved = await apiService.submitReservationData(
        formData.roomId,
        formData.reservationDate,
        eventId
      );

      if (!isReservationSaved) {
        setErrors({
          api: "Falha ao salvar a reserva. Tente novamente mais tarde.",
        });
        return;
      }

      const event_submission = await apiService.submitEventData(
        formData,
        "requested",
        eventId
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
      <div className="dados-preview">
        <pre>{JSON.stringify(formData, null, 2)}</pre>
      </div>
      <button className="btn btn-primary" onClick={handleConfirm}>
        Confirmar
      </button>
    </div>
  );
};

export default EventConfirmData;
