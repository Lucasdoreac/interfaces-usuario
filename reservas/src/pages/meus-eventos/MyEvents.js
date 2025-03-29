import React, { useEffect, useState } from "react";
import apiService from "../../services/client";
import { Link } from "react-router-dom";
import Loading from "../../components/Loading";

const MyEvents = () => {
  const [events, setEvents] = useState([]);
  const [mergedData, setMergedData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const userEmail = localStorage.getItem("userEmail");

  useEffect(() => {
    const fetchUserEvents = async () => {
      try {
        setLoading(true);
        setError(null);

        // Buscar todos os eventos do usuário
        const eventsResponse = await apiService.getUserEvents(userEmail);
        if (!eventsResponse || !eventsResponse.events) {
          setEvents([]);
          return;
        }

        const userEvents = eventsResponse.events;
        setEvents(userEvents);

        // Para cada evento, buscar reserva e depois buscar o nome da sala
        const mergedArray = await Promise.all(
          userEvents.map(async (evento) => {
            const reservationData = await apiService.getEventsReservations(
              evento._id
            );
            const reservation = Array.isArray(reservationData)
              ? reservationData[0]
              : reservationData;

            let room = null;
            if (reservation && reservation.roomId) {
              room = await apiService.getRoomById(reservation.roomId);
            }

            return {
              ...evento,
              reservation,
              room,
            };
          })
        );

        setMergedData(mergedArray);
      } catch (err) {
        console.error(err);
        setError("Erro ao buscar eventos e reservas.");
      } finally {
        setLoading(false);
      }
    };

    if (userEmail) {
      fetchUserEvents();
    }
  }, [userEmail]);

  if (error) return <p>{error}</p>;

  return (
    <div className="meus-eventos-container">
      <h2>Meus Eventos</h2>
      {loading ? (
        <div className="d-flex justify-content-center align-items-center">
          <Loading />
        </div>
      ) : mergedData.length === 0 ? (
        <div className="d-flex flex-column align-items-center">
          <p>Você ainda não possui eventos cadastrados.</p>
          <Link className="btn btn-primary text-white" to="/event/basic-info">
            Cadastrar Evento
          </Link>
        </div>
      ) : (
        <ul>
          {mergedData.map((item) => {
            const { reservation, room } = item;

            let sala = "Indefinido";
            let dia = "Indefinido";
            let horario = "Indefinido";

            if (room) {
              sala = room.name || sala;
            }

            if (reservation && reservation.startAt) {
              const startAt = new Date(reservation.startAt);
              dia = startAt.toLocaleDateString("pt-BR");
              const endAt = new Date(reservation.endAt);
              horario = `${startAt.toLocaleTimeString("pt-BR", {
                hour: "2-digit",
                minute: "2-digit",
              })} - ${endAt.toLocaleTimeString("pt-BR", {
                hour: "2-digit",
                minute: "2-digit",
              })}`;
            }

            return (
              <li key={item.id} className="evento-item">
                <h3>{item.name}</h3>
                <p>Sala: {sala}</p>
                <p>Dia: {dia}</p>
                <p>Horário: {horario}</p>
                <p>Status: {item.status}</p>
              </li>
            );
          })}
          <div className="d-flex flex-column align-items-center">
            <Link className="btn btn-primary text-white" to="/event/basic-info">
              Cadastrar Evento
            </Link>
          </div>
        </ul>
      )}
    </div>
  );
};

export default MyEvents;
