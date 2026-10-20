import React, { useEffect, useState, useCallback } from 'react';
import InfiniteScroll from 'react-infinite-scroll-component';
import apiService from '../../services/client';
import './InfiniteScrollRooms.scss';

const InfiniteScrollRooms = ({ date, time, onRoomSelect, userSearchInput = "" }) => {
  const [rooms, setRooms] = useState([]);
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const [hasMore, setHasMore] = useState(true);
  const [selectedRoomId, setSelectedRoomId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Formata a data para o formato "YYYY-MM-DD"
  const formattedDate = date.toISOString().split('T')[0];

  // Use useCallback to prevent recreating this function on every render
  const fetchRooms = useCallback(async (currentPage = 1, resetData = false) => {
    if (isLoading) return;
    
    setIsLoading(true);
    if(resetData) setRooms([]);
    setError(null);
    try {
      const response = await apiService.getAvailableSlots(
        formattedDate, 
        time, 
        currentPage, 
        pageSize, 
        userSearchInput
      );
      
      if (response && response.data) {
        const newRooms = response.data;
        
        setRooms(prevRooms => {
          const updatedRooms = resetData ? newRooms : [...prevRooms, ...newRooms];
          return updatedRooms;
        });

        // Atualiza a página e verifica se há mais dados com base na paginação
        if (newRooms.length === 0 || (response.pagination && currentPage >= response.pagination.total_pages)) {
          setHasMore(false);
        } else {
          setPage(currentPage + 1);
          setHasMore(true);
        }
      } else {
        setHasMore(false);
      }
    } catch (error) {
      console.error("Erro ao buscar salas disponíveis:", error);
      setError(error.response?.data?.error || "Erro ao carregar salas");
      setHasMore(false);
    } finally {
      setIsLoading(false);
    }
  }, [formattedDate, time, pageSize, userSearchInput]);
  
  useEffect(() => {
    setError(null);
  }, [userSearchInput]);

  useEffect(() => {
    setPage(1);
    setHasMore(true);
    setSelectedRoomId(null);
    fetchRooms(1, true);
  }, [formattedDate, time, userSearchInput, fetchRooms]);

  const loadMoreRooms = () => {    
    if (!isLoading && hasMore) {
      fetchRooms(page);
    }
  };

  const handleSelectRoom = (roomId) => {
    setSelectedRoomId(roomId);
    if (onRoomSelect) {
      onRoomSelect(roomId);
    }
  };

  return (
    error ? (
      <div className="error-message">{error}</div>
    ) : (
      <div id="scrollableDiv" style={{ height: '60vh', overflow: 'auto' }}>
        <InfiniteScroll
          dataLength={rooms.length}
          next={loadMoreRooms}
          hasMore={hasMore}
          loader={<h4>Carregando mais salas...</h4>}
          endMessage={<p>Você chegou ao fim da lista.</p>}
          scrollableTarget="scrollableDiv"
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
              isLoading ? (
                <p>Carregando...</p>
              ) : (
                <p>Nenhuma sala encontrada.</p>
              )
            )}
          </div>
        </InfiniteScroll>
      </div>
    )
  );
};

export default InfiniteScrollRooms;