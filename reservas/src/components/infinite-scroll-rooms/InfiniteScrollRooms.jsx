import React, { useEffect, useState } from 'react';
import InfiniteScroll from 'react-infinite-scroll-component';
import apiService from '../../services/client';
import './InfiniteScrollRooms.scss';

const InfiniteScrollRooms = ({ date, time, onRoomSelect }) => {
  const [rooms, setRooms] = useState([]);
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const [hasMore, setHasMore] = useState(true);
  const [selectedRoomId, setSelectedRoomId] = useState(null);

  // Formata a data para o formato "YYYY-MM-DD"
  const formattedDate = date.toISOString().split('T')[0];

  const fetchRooms = async () => {
    try {
      const response = await apiService.getAvailableSlots(formattedDate, time, page, pageSize);
      if (response && response.data) {
        const newRooms = response.data;
        setRooms(prevRooms => [...prevRooms, ...newRooms]);

        // Atualiza a página e verifica se há mais dados com base na paginação
        if (page >= response.pagination.total_pages) {
          setHasMore(false);
        } else {
          setPage(page + 1);
        }
      } else {
        setHasMore(false);
      }
    } catch (error) {
      console.error("Erro ao buscar salas disponíveis:", error);
      setHasMore(false);
    }
  };

  // Reinicia a busca quando a data ou horário muda
  useEffect(() => {
    setRooms([]);
    setPage(1);
    setHasMore(true);
    setSelectedRoomId(null);
    fetchRooms();
  }, [date, time]);

  const handleSelectRoom = (roomId) => {
    setSelectedRoomId(roomId);
    if (onRoomSelect) {
      onRoomSelect(roomId);
    }
  };

  return (
    <InfiniteScroll
    
      dataLength={rooms.length}
      next={fetchRooms}
      hasMore={hasMore}
      loader={<h4>Carregando mais salas...</h4>}
      endMessage={<p>Você chegou ao fim da lista.</p>}
    >
      
      <div className="rooms-list">
        {rooms.map(room => (
          <div
            key={room.id}
            className={`room-card ${selectedRoomId === room.id ? 'selected' : ''}`}
            onClick={() => handleSelectRoom(room.id)}
          >
            <h3>{room.name}</h3>
            <p>{room.campus}</p>
          </div>
        ))}
      </div>
    </InfiniteScroll>
  );
};

export default InfiniteScrollRooms;
