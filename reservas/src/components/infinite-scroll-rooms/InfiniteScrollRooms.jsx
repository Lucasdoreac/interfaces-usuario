import React, { useEffect, useRef, useState } from 'react';
import InfiniteScroll from 'react-infinite-scroll-component';
import apiService from '../../services/client';
import { createRoomsLoader } from './roomPagination.js';
import './InfiniteScrollRooms.scss';

const InfiniteScrollRooms = ({ date, time, onRoomSelect, userSearchInput = "" }) => {
  const pageSize = 10;
  const [{ rooms, hasMore, error }, setLoaderState] = useState({
    rooms: [],
    hasMore: true,
    error: null,
  });
  const [selectedRoomId, setSelectedRoomId] = useState(null);

  // Formata a data para o formato "YYYY-MM-DD"
  const formattedDate = date.toISOString().split('T')[0];

  // O controlador descarta respostas de filtros antigos e guarda o pedido em andamento.
  const loaderRef = useRef(null);
  if (!loaderRef.current) {
    loaderRef.current = createRoomsLoader({
      fetchPage: (page, filter) =>
        apiService.getAvailableSlots(filter.date, filter.time, page, pageSize, filter.search),
      onChange: setLoaderState,
    });
  }
  const loader = loaderRef.current;

  // Reinicia e busca a primeira página quando os filtros mudam
  useEffect(() => {
    setSelectedRoomId(null);
    loader.setFilter({ date: formattedDate, time, search: userSearchInput });
    return () => loader.cancel();
  }, [loader, formattedDate, time, userSearchInput]);

  const loadMoreRooms = () => loader.loadMore();

  const handleSelectRoom = (roomId) => {
    setSelectedRoomId(roomId);
    if (onRoomSelect) {
      onRoomSelect(roomId);
    }
  };

    return (
    error ? (
      <div className="error-message" role="alert">
        <p>{error}</p>
        <button type="button" className="btn btn-outline-primary" onClick={() => loader.retry()}>
          Tentar novamente
        </button>
      </div>
    ) : (
      <InfiniteScroll
        dataLength={rooms.length}
        next={loadMoreRooms}
        hasMore={hasMore}
        loader={<h4>Carregando mais salas...</h4>}
        endMessage={<p>Você chegou ao fim da lista.</p>}
      >
        <div className="rooms-list">
          {rooms.length > 0 ? (
            rooms.map((room) => (
              <div
                key={room.id}
                className={`room-card ${selectedRoomId === room.id ? "selected" : ""}`}
                onClick={() => handleSelectRoom(room.id)}
              >
                <h3>{room.name}</h3>
                <p>{room.campus}</p>
              </div>
            ))
          ) : (
            <p>Nenhuma sala encontrada.</p>
          )}
        </div>
      </InfiniteScroll>
    )
  );
};

export default InfiniteScrollRooms;
