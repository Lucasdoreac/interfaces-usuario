import React, { useState } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate } from "react-router-dom";
import { useFormContext } from "../../context/FormContext";
import apiService from "../../services/client";

const EventConfirmData = () => {
  const navigate = useNavigate();
  const { formData, eventId } = useFormContext();
  const [errors, setErrors] = useState({});

  const handleConfirm = async () => {
    if (validateForm()) {
      try {
        const isReservationSaved = await apiService.submitReservationData(
          formData.roomId,
          formData.reservationDate,
          eventId
        );
        if (!isReservationSaved) {
          alert("Falha ao salvar a reserva.");
          return;
        }

        await apiService.submitEventData(formData, "requested", eventId);
        console.log("Form submitted", eventId);
        navigate(`/event/confirmation?eventId=${eventId}`);
      } catch (error) {
        console.error("Error submitting:", error);
      }
    }
  };

  const validateForm = () => {
    const newErrors = {};
    if (
      !formData.numeroParticipantes?.trim() ||
      formData.numeroParticipantes <= 0
    )
      newErrors.numeroParticipantes = "Número de participantes é obrigatório.";
    if (!formData.espacos?.trim())
      newErrors.espacos = "Selecione um espaço necessário.";
    if (formData.trilha === "sim" && !formData.trilhaDesc?.trim())
      newErrors.trilhaDesc = "Descrição da trilha empreendedora é obrigatória.";
    if (formData.projeto === "sim" && !formData.projetoDesc?.trim())
      newErrors.projetoDesc = "Descrição do projeto de extensão é obrigatória.";
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
