import React, { useState } from "react";
import DatePickerComponent from "../../components/date-picker/DatePickerComponent";
import InfiniteScrollRooms from "../../components/infinite-scroll-rooms/InfiniteScrollRooms";
import { useNavigate } from "react-router-dom";
import { useFormContext } from "../../context/FormContext";
import "./EscolhaHorario.scss";

const EscolheHorario = () => {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [selectedPeriod, setSelectedPeriod] = useState();
  const [selectedRoom, setSelectedRoom] = useState(null);
  const { handleRoomDataChange, handleSaveDraft } = useFormContext();
  const navigate = useNavigate();

  const periodToTime = {
    Manhã: "08:00:00",
    Tarde: "14:00:00",
    Noite: "19:00:00",
  };

  const selectedTime = periodToTime[selectedPeriod];

  const handleDateChange = (date) => {
    setSelectedDate(date);
  };

  const handlePeriodChange = (e) => {
    setSelectedPeriod(e.target.value);
  };

  const handleRoomSelect = (roomId) => {
    setSelectedRoom(roomId);
    handleRoomDataChange(roomId, selectedDate);

  };

  const handleContinue = () => {
    handleSaveDraft();
    navigate("/proximo-passo");
  };

  return (
    <div className="escolha-horario-container">
      <div className="header-container">
        <h2>Escolha o Dia e Horário</h2>
        <DatePickerComponent
          selectedDate={selectedDate}
          onDateChange={handleDateChange}
        />

        <div className="period-selection">
          <p>Selecione o período:</p>
          <label>
            <input
              type="radio"
              value="Manhã"
              checked={selectedPeriod === "Manhã"}
              onChange={handlePeriodChange}
            />
            Manhã
          </label>
          <label>
            <input
              type="radio"
              value="Tarde"
              checked={selectedPeriod === "Tarde"}
              onChange={handlePeriodChange}
            />
            Tarde
          </label>
          <label>
            <input
              type="radio"
              value="Noite"
              checked={selectedPeriod === "Noite"}
              onChange={handlePeriodChange}
            />
            Noite
          </label>
        </div>
        {selectedRoom && (
          <div className="continue-button-containers">
            <button
              className="btn btn-primary continue-button"
              onClick={handleContinue}
            >
              Continuar
            </button>
          </div>
        )}
      </div>

      <div className="scroll-container">
        {selectedPeriod && (
          <>
            <h3>
              Salas disponíveis para {selectedDate.toLocaleDateString()} às{" "}
              {selectedTime}:
            </h3>
            <InfiniteScrollRooms
              date={selectedDate}
              time={selectedTime}
              onRoomSelect={handleRoomSelect}
            />
          </>
        )}
      </div>
    </div>
  );
};

export default EscolheHorario;
