import React, { useState } from "react";
import { AiOutlineLeft, AiOutlineSearch } from "react-icons/ai";
import DatePickerComponent from "../../components/date-picker/DatePickerComponent";
import InfiniteScrollRooms from "../../components/infinite-scroll-rooms/InfiniteScrollRooms";
import { useNavigate } from "react-router-dom";
import { useFormContext } from "../../context/FormContext";
import "./EventSchedule.scss";

const EventSchedule = () => {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [selectedPeriod, setSelectedPeriod] = useState();
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const { handleRoomDataChange, eventId } = useFormContext();
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
    handleRoomDataChange(roomId, selectedDate, eventId);
  };

  const handleContinue = () => {
    navigate(`/event/confirm-data?eventId=${eventId}`); // Add eventId as a query parameter
  };

  // Debounce para a busca
  const handleSearchChange = (e) => {
    const value = e.target.value;
    setSearchQuery(value);
    
    // Debounce para evitar muitas requisições durante a digitação
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => {
      setDebouncedQuery(value);
    }, 500);
  };

  return (
    <div className="escolha-horario-container">
      <div className="card-header">
        <span onClick={() => navigate(`/event/logistics?eventId=${eventId}`)}>
          <AiOutlineLeft
            size="20px"
            color="white"
            style={{ marginRight: 10 }}
          />
        </span>
      </div>
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
            
            {/* Barra de pesquisa */}
            <div className="search-container">
              <div className="search-input-wrapper">
                <AiOutlineSearch className="search-icon" />
                <input
                  type="text"
                  placeholder="Pesquisar salas por nome..."
                  value={searchQuery}
                  onChange={handleSearchChange}
                  className="search-input"
                />
              </div>
            </div>
            
            <InfiniteScrollRooms
              date={selectedDate}
              time={selectedTime}
              onRoomSelect={handleRoomSelect}
              roomName={debouncedQuery}
            />
          </>
        )}
      </div>
    </div>
  );
};

export default EventSchedule;