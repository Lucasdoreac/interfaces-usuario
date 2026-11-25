import React, { useState } from "react";
import { AiOutlineLeft, AiOutlineSearch } from "react-icons/ai";
import DatePickerComponent from "../../components/date-picker/DatePickerComponent";
import InfiniteScrollRooms from "../../components/infinite-scroll-rooms/InfiniteScrollRooms";
import { useNavigate, useLocation } from "react-router";
import { useFormContext } from "../../context/FormContext";
import { todayInBrasilia, civilDayToPicker, pickerToCivilDay, brasiliaCivilToInstant } from "../../utils/dateUtils";
import "./EventSchedule.scss";

const EventSchedule = () => {
  const [selectedDay, setSelectedDay] = useState(() => todayInBrasilia());
  const [selectedPeriod, setSelectedPeriod] = useState("Manha");
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");

  // Pego o eventId e a classificação (tipo de evento) do contexto do formulário
  const { handleRoomDataChange, clearRoomData, formData } = useFormContext();
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const eventId = queryParams.get("eventId");

  const periodToTime = {
    Manha: "08:00:00",
    Tarde: "14:00:00",
    Noite: "19:00:00",
  };

  const selectedTime = periodToTime[selectedPeriod];

  let selectedDate = null;
  try { selectedDate = brasiliaCivilToInstant(selectedDay, selectedTime); } catch { /* fail closed */ }
  const clearSelection = () => {
    setSelectedRoom(null);
    clearRoomData();
  };
  const handleDateChange = (date) => {
    if (!date) return;
    const next = pickerToCivilDay(date);
    if (next !== selectedDay) {
      clearSelection();
      setSelectedDay(next);
    }
  };
  const handlePeriodChange = (e) => {
    const period = e.target.value;
    if (period === selectedPeriod) return;
    clearSelection();
    setSelectedPeriod(period);
  };

  const handleRoomSelect = (roomId) => {
    if (!selectedDate) return;
    setSelectedRoom(roomId);
    handleRoomDataChange(roomId, selectedDate, eventId);
  };

  const handleContinue = () => {
    navigate(`/event/confirm-data?eventId=${eventId}`);
  };

  // Função para lidar com o botão voltar com lógica condicional
  const handleGoBack = () => {
    // Verifica o tipo do evento atual
    const eventType = formData.classificacao;

    if (eventType === "class" || eventType === "exam") {
      // Se for aula ou exame, volta para a tela de seleção de tipo
      navigate(`/event/type-selection${eventId ? `?eventId=${eventId}` : ""}`);
    } else {
      // Caso contrário, mantém o comportamento original
      navigate(`/event/logistics${eventId ? `?eventId=${eventId}` : ""}`);
    }
  };

  // Debounce para a busca
  const handleSearchChange = (e) => {
    const value = e.target.value;
    clearSelection();
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
        {/* Substitui a navegação direta por um handler condicional */}
        <span onClick={handleGoBack}>
          <AiOutlineLeft
            size="20px"
            color="white"
            style={{ marginRight: 10 }}
          />
        </span>
      </div>
      <div className="header-container">
        <h1 className="h2">Escolha o Dia e Horário</h1>
        <DatePickerComponent
          selectedDate={civilDayToPicker(selectedDay)}
          minDate={civilDayToPicker(todayInBrasilia())}
          onDateChange={handleDateChange}
        />
        <div className="period-selection">
          <p>Selecione o período:</p>
          <label>
            <input
              type="radio"
              value="Manha"
              checked={selectedPeriod === "Manha"}
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
              type="button"
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
              Salas disponíveis para {selectedDay.split("-").reverse().join("/")} às{" "}
              {selectedTime} (horário de Brasília):
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

            {!selectedDate ? <p role="alert">Horário inexistente ou ambíguo em Brasília. Escolha outra data ou período.</p> : searchQuery !== debouncedQuery ? <p>Atualizando pesquisa...</p> : <InfiniteScrollRooms
              key={`${selectedDay}-${selectedTime}`}
              startAt={selectedDate.toISOString()}
              onRoomSelect={handleRoomSelect}
              userSearchInput={debouncedQuery}
            />}
          </>
        )}
      </div>
    </div>
  );
};

export default EventSchedule;
