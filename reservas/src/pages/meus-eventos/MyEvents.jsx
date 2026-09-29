import React, { useEffect, useState } from "react";
import { Link } from "react-router";
import apiService from "../../services/client";
import Loading from "../../components/Loading";
import { useFormContext } from "../../context/FormContext";
import EventStatus from "../../utils/EventStatus";

const MyEvents = () => {
  const { eventTypes, odsTypes, targetPublicTypes, resourcesTypes } =
    useFormContext();
  const [mergedData, setMergedData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const userEmail = localStorage.getItem("userEmail");

  // Status text and color mapping
  const getStatusText = (status) => {
    switch (status) {
      case EventStatus.WAITING:
        return "Aguardando";
      case EventStatus.APPROVED_BY_COORDENACAO:
        return "Aprovado pela Coordenação";
      case EventStatus.REJECTED_BY_COORDENACAO:
        return "Rejeitado pela Coordenação";
      case EventStatus.APPROVED_BY_REITORIA:
        return "Aprovado pela Reitoria";
      case EventStatus.REJECTED_BY_REITORIA:
        return "Rejeitado pela Reitoria";
      case EventStatus.REQUESTED_CHANGE:
        return "Alterações Solicitadas";
      case EventStatus.DIRECT_APPROVAL:
        return "Aprovado Diretamente";
      case EventStatus.Draft:
        return "Rascunho";
      default:
        return status || "Desconhecido";
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case EventStatus.WAITING:
        return "warning";
      case EventStatus.APPROVED_BY_COORDENACAO:
      case EventStatus.APPROVED_BY_REITORIA:
      case EventStatus.DIRECT_APPROVAL:
        return "success";
      case EventStatus.REJECTED_BY_COORDENACAO:
      case EventStatus.REJECTED_BY_REITORIA:
        return "danger";
      case EventStatus.REQUESTED_CHANGE:
        return "warning";
      case EventStatus.DRAFT:
        return "secondary";
      default:
        return "info";
    }
  };

  const canEditEvent = (status) => {
    return (
      status === EventStatus.REQUESTED_CHANGE || status === EventStatus.DRAFT
    );
  };

  useEffect(() => {
    const fetchUserEvents = async () => {
      try {
        setLoading(true);
        setError(null);

        // Buscar todos os eventos do usuário
        const eventsResponse = await apiService.getUserEvents(userEmail);
        if (!eventsResponse || !eventsResponse.events) {
          setMergedData([]);
          return;
        }

        const userEvents = eventsResponse.events;

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

            let course = null;
            if (evento.graduationId) {
              try {
                course = await apiService.getCourseById(evento.graduationId);
              } catch (err) {
                console.error("Erro ao buscar curso:", err);
              }
            }

            return {
              ...evento,
              reservation,
              room,
              course,
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
    <div className="container my-4">
      <h2 className="mb-4">Meus Eventos</h2>
      {loading ? (
        <div className="d-flex justify-content-center align-items-center">
          <Loading />
        </div>
      ) : mergedData.length === 0 ? (
        <div className="text-center">
          <p>Você ainda não possui eventos cadastrados.</p>
          <Link
            className="btn btn-primary text-white"
            to="/event/type-selection"
          >
            Cadastrar Evento
          </Link>
        </div>
      ) : (
        <div className="row">
          {mergedData.map((item) => {
            const { reservation, room, course } = item;
            let sala = room && room.name ? room.name : "Indefinido";
            let dia = "Indefinido";
            let horario = "Indefinido";
            if (reservation && reservation.startAt) {
              // Create Date objects from the strings
              const startAt = new Date(reservation.startAt);
              const endAt = new Date(reservation.endAt);

              // Format date normally for the day display
              dia = startAt.toLocaleDateString("pt-BR");

              // Format time using UTC methods to preserve the original hours
              horario = `${startAt
                .getUTCHours()
                .toString()
                .padStart(2, "0")}:${startAt
                .getUTCMinutes()
                .toString()
                .padStart(2, "0")} - 
                         ${endAt
                           .getUTCHours()
                           .toString()
                           .padStart(2, "0")}:${endAt
                .getUTCMinutes()
                .toString()
                .padStart(2, "0")}`;
            }

            // Verifica se o evento pode ser editado usando a função auxiliar
            const canEdit = canEditEvent(item.status);

            // Encontrar o nome do tipo de evento
            const eventTypeObj = eventTypes.find(
              (et) => et.type === item.eventTypeId
            );
            const eventTypeName = eventTypeObj
              ? eventTypeObj.name
              : "Tipo Indefinido";

            // Usar as funções auxiliares para status e cor
            const statusText = getStatusText(item.status);
            const badgeColor = getStatusColor(item.status);

            // ODS e Público-Alvo
            const ods =
              odsTypes.find((o) => o.id == item.odsId)?.formatted ||
              "Indefinido"; // == because id is number and odsId is string
            const targetPublicLabels =
              item.targetPublic && item.targetPublic.length > 0
                ? item.targetPublic
                    .map((tp) => {
                      const targetObj = targetPublicTypes.find(
                        (t) => t.id === tp
                      );
                      return targetObj ? targetObj.label : "Não definido";
                    })
                    .join(", ")
                : "Indefinido";

            const resourcesLabels =
              item.resources && item.resources.length > 0
                ? item.resources
                    .map((r) => {
                      const resourceObj = resourcesTypes.find(
                        (t) => t.id === r
                      );
                      return resourceObj ? resourceObj.label : "Não definido";
                    })
                    .join(", ")
                : "Indefinido";

            return (
              <div className="col-md-6 mb-4" key={item._id}>
                <div className="card h-100 shadow">
                  {item.eventLogo && (
                    <img
                      src={item.eventLogo}
                      className="card-img-top"
                      alt={`${item.name} logo`}
                    />
                  )}
                  <div className="card-header text-center">
                    <h5 className="mb-0">
                      {item.name}{" "}
                      <span className={`badge bg-${badgeColor}`}>
                        {statusText}
                      </span>
                    </h5>
                  </div>
                  <div className="card-body">
                    <p className="card-title">{eventTypeName}</p>
                    <h6 className="card-subtitle card-muted">
                      <strong>Descrição:</strong>{" "}
                      {item.description || "Sem descrição"}
                    </h6>
                    {item.entrepreneuralPath && (
                      <h6 className="card-subtitle card-muted">
                        <strong>Caminho Empreendedor:</strong>{" "}
                        {item.entrepreneuralPath}
                      </h6>
                    )}
                    {item.expectedSubscribers && (
                      <h6 className="card-subtitle card-muted">
                        <strong>Inscritos Esperados:</strong>{" "}
                        {item.expectedSubscribers}
                      </h6>
                    )}
                    {item.extensionProject && (
                      <h6 className="card-subtitle card-muted">
                        <strong>Projeto de Extensão:</strong>{" "}
                        {item.extensionProject}
                      </h6>
                    )}
                    <h6 className="card-subtitle card-muted">
                      <strong>Graduação:</strong>{" "}
                      {course ? course.name : "Indefinido"}
                    </h6>
                    <h6 className="card-subtitle card-muted">
                      <strong>ODS:</strong> {ods}
                    </h6>
                    {item.organizer && (
                      <h6 className="card-subtitle card-muted">
                        <strong>Organizador:</strong> {item.organizer.name}{" "}
                        {`(${item.organizer.email}, ${item.organizer.phone})`}
                      </h6>
                    )}
                    {item.resources && item.resources.length > 0 && (
                      <h6 className="card-subtitle card-muted">
                        <strong>Recursos:</strong> {resourcesLabels}
                      </h6>
                    )}
                    {item.roomType && (
                      <h6 className="card-subtitle card-muted">
                        <strong>Tipo de Sala:</strong> {item.roomType}
                      </h6>
                    )}
                    {item.studentsMonitors &&
                      Array.isArray(item.studentsMonitors) &&
                      item.studentsMonitors.length > 0 && (
                        <h6 className="card-subtitle card-muted">
                          <strong>Monitores:</strong>{" "}
                          {item.studentsMonitors.join(", ")}
                        </h6>
                      )}
                    {item.subscriptionLink && (
                      <h6 className="card-subtitle card-muted">
                        <strong>Link de Inscrição:</strong>{" "}
                        <a
                          href={item.subscriptionLink}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {item.subscriptionLink}
                        </a>
                      </h6>
                    )}
                    <h6 className="card-subtitle card-muted">
                      <strong>Público Alvo:</strong> {targetPublicLabels}
                    </h6>
                    {canEdit && (
                      <Link
                        className="btn btn-outline-warning mt-2"
                        to={`/event/type-selection?eventId=${item._id}`}
                      >
                        Editar Evento
                      </Link>
                    )}
                  </div>
                  <div className="card-footer text-muted text-center">
                    <p className="mb-0">
                      <strong>Reserva:</strong> Sala: {sala} | Dia: {dia} |
                      Horário: {horario}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
          <div className="col-12 text-center mt-3">
            <Link
              className="btn btn-primary text-white"
              to="/event/type-selection"
            >
              Cadastrar Evento
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};

export default MyEvents;
