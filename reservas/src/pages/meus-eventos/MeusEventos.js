import React, { useEffect, useState } from "react";
import apiService from "../../services/client";

const MeusEventos = () => {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Recupera o email do usuário (já armazenado no FormContext ou localStorage)
  const userEmail = localStorage.getItem("userEmail");

  useEffect(() => {
    const fetchUserEvents = async () => {
      try {
        setLoading(true);
        const response = await apiService.getUserEvents(userEmail);
        setEvents(response.events || []);
      } catch (err) {
        setError("Erro ao buscar eventos.");
      } finally {
        setLoading(false);
      }
    };

    if (userEmail) {
      fetchUserEvents();
    }
  }, [userEmail]);

  if (loading) return <p>Carregando seus eventos...</p>;
  if (error) return <p>{error}</p>;

  return (
    <div className="meus-eventos-container">
      <h2>Meus Eventos</h2>
      {events.length === 0 ? (
        <p>Você ainda não possui eventos cadastrados.</p>
      ) : (
        <ul>
          {events.map((evento) => (
            <li key={evento.id} className="evento-item">
              <h3>{evento.name}</h3>
              <p>Status: {evento.status}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default MeusEventos;
