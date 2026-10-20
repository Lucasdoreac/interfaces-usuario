import React, { useEffect, useState } from "react";
import { AiOutlineLeft, AiOutlineSearch } from "react-icons/ai";
import DatePickerComponent from "../../components/date-picker/DatePickerComponent";
import InfiniteScrollRooms from "../../components/infinite-scroll-rooms/InfiniteScrollRooms";
import { useNavigate, useLocation } from "react-router-dom";
import { useFormContext } from "../../context/FormContext";
import "./EventSchedule.scss";
import { ThemeContext } from "../../context/ThemeContext";
import { useContext } from "react";

const EventSchedule = () => {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [selectedPeriod, setSelectedPeriod] = useState("Manha");
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const {theme} = useContext(ThemeContext);

  // Pego o eventId e a classificação (tipo de evento) do contexto do formulário
  const { handleRoomDataChange, formData } = useFormContext();
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const eventId = queryParams.get("eventId");

  const periodToTime = {
    Manha: "08:00:00",
    Tarde: "14:00:00",
    Noite: "19:00:00",
  };

  const [selectedTime, setSelectedTime] = useState(
    periodToTime[selectedPeriod]
  );

  // Update selectedTime and adjust selectedDate when selectedPeriod changes
  useEffect(() => {
    if (selectedPeriod) {
      const time = periodToTime[selectedPeriod];
      setSelectedTime(time);

      // Update the hour of selectedDate based on the selected period
      const [hours, minutes, seconds] = time.split(":").map(Number);
      const updatedDate = new Date(selectedDate);
      updatedDate.setHours(hours, minutes, seconds);
      setSelectedDate(updatedDate);
    }
  }, [selectedPeriod]);

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
      <div className="header-container"
    style={{marginLeft: "10px"}}>
      
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
              style={{marginLeft: "10px"}}
            />
            Tarde
          </label>
          <label>
            <input
              type="radio"
              value="Noite"
              checked={selectedPeriod === "Noite"}
              onChange={handlePeriodChange}
              style={{marginLeft: "10px"}}
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
              userSearchInput={debouncedQuery}
            />
          </>
        )}
      </div>
    </div>
  );
};

export default EventSchedule;
