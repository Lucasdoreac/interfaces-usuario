import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import apiService from "../services/client";
import EventStatus from "../utils/EventStatus";
import { formatDateForMongoDB } from "../utils/dateUtils";

const FormContext = createContext();

export const FormProvider = ({ children }) => {
  // State for form data
  const [formData, setFormData] = useState(() => {
    const savedData = localStorage.getItem("formData");
    return savedData ? JSON.parse(savedData) : {};
  });
  const [eventId, setEventId] = useState("");

  // State for types data from API
  const [eventTypes, setEventTypes] = useState([]);
  const [odsTypes, setOdsTypes] = useState([]);
  const [resourcesTypes, setResources] = useState([]);
  const [targetPublicTypes, setTargetPublic] = useState([]);
  const [roomTypes, setRoomTypes] = useState({});
  const [logoUrl, setLogoUrl] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    localStorage.setItem("formData", JSON.stringify(formData));
  }, [formData]);

  // Fetch types data from API and store in context
  useEffect(() => {
    const fetchTypes = async () => {
      try {
        const data = await apiService.getTypes();
        if (data?.types) {
          const eventsData = data.types.find(
            (item) => item.collection === "events"
          );
          const odsData = data.types.find((item) => item.collection === "ODS");
          setEventTypes(eventsData?.types || []);
          // Store ODS types as objects with a formatted string for display
          setOdsTypes(
            odsData?.types.map((ods) => ({
              id: ods.id,
              name: ods.name,
              type: ods.type,
              formatted: `${ods.id} - ${ods.name} (${ods.type})`,
            })) || []
          );
          const resourcesData = data.types.find(
            (item) => item.collection === "resources"
          );
          const targetPublicData = data.types.find(
            (item) => item.collection === "targetPublic"
          );
          setResources(resourcesData?.types || []);
          setTargetPublic(targetPublicData?.types || []);
          const roomTypesData = data.types.find(
            (item) => item.collection === "rooms"
          );
          setRoomTypes(roomTypesData?.types || []);
        }
      } catch (error) {
        console.error("Failed to fetch types data:", error);
      }
    };
    fetchTypes();
  }, []);

  /**
   * fillOutFormData:
   * If an eventId is provided, fetch the event from the user's events response,
   * map its fields to match the form field names, update context state and localStorage.
   * If an empty string is provided, reset formData and clear eventId.
   */
  const fillOutFormData = useCallback(async (eventId = "") => {
    localStorage.setItem("eventId", eventId);
    localStorage.removeItem("formData");

    if (!eventId) {
      // New event: clear form data
      setFormData({});
      localStorage.removeItem("eventId");
      localStorage.removeItem("formData");
      return;
    }
    setEventId(eventId);
    try {
      const userEmail = localStorage.getItem("userEmail");
      const response = await apiService.getUserEvents(userEmail);
      const events = response?.events || [];
      const eventToEdit = events.find(
        (event) => String(event._id) === String(eventId)
      );
      if (eventToEdit) {
        // Map API fields to the form's expected names.
        const mappedEvent = await fromApiAnswerToFormData(eventToEdit);
        setFormData(mappedEvent);
        localStorage.setItem("formData", JSON.stringify(mappedEvent));
        localStorage.setItem("eventId", eventId);
      } else {
        setFormData({});
        localStorage.removeItem("eventId");
      }
    } catch (error) {
      console.error("Error fetching event data:", error);
    }
  }, []);

  const fromApiAnswerToFormData = async (eventToEdit) => {
    const course = await apiService.getCourseById(eventToEdit.graduationId);
    const courseName = course?.name || "";

    return {
      tituloEvento: eventToEdit.name,
      telefone: eventToEdit.organizer.phone,
      classificacao: eventToEdit.eventTypeId,
      ods: eventToEdit.odsId,
      odsId: eventToEdit.odsId,
      odsName: odsTypes.find(
        (ods) => String(ods.id) === String(eventToEdit.odsId)
      )?.formatted,
      descricaoEvento: eventToEdit.description,
      courseId: eventToEdit.graduationId,
      courseName: courseName,
      publicoAlvo: eventToEdit.targetPublic,
      recursosNecessarios: eventToEdit.resources,
      numeroParticipantes: eventToEdit.expectedSubscribers,
      espacos: eventToEdit.roomType,
      trilha: eventToEdit.entrepreneuralPath ? "sim" : "nao",
      trilhaDesc: eventToEdit.entrepreneuralPath,
      projeto: eventToEdit.extensionProject ? "sim" : "nao",
      projetoDesc: eventToEdit.extensionProject,
      alunosMonitores: eventToEdit.studentsMonitors,
      logo: "dwcorp.com.br:9000/labtech/email-icones/magic-link.png",
    };
  };

  const saveDraft = async () => {
    try {
      const draftId = await apiService.submitEventData(
        formData,
        EventStatus.DRAFT,
        eventId || ""
      );
      localStorage.setItem("eventId", draftId);
      setEventId(draftId);
      return draftId;
    } catch (error) {
      console.error("Erro ao salvar draft:", error);
      return null;
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prevData) => ({ ...prevData, [name]: value }));
  };

  // Updated handleOdsChange: use the selected ODS id and lookup its name if available
  const handleOdsChange = (e) => {
    const selectedOdsId = e.target.value;
    const selectedOds = odsTypes.find(
      (ods) => String(ods.id) === String(selectedOdsId)
    );
    setFormData((prevData) => ({
      ...prevData,
      ods: selectedOdsId,
      odsId: selectedOdsId,
      odsName: selectedOds ? selectedOds.name : "",
    }));
  };

  const handleCursoChanged = (name, id) => {
    setFormData((prevData) => ({
      ...prevData,
      courseId: id,
      courseName: name,
    }));
  };

  const handleRoomDataChange = (roomId, reservationDate, eventId) => {
    setFormData((prevData) => ({
      ...prevData,
      roomId,
      reservationDate: formatDateForMongoDB(reservationDate),
      eventId,
    }));
  };

  const handleSaveAlunoMonitor = (alunos) => {
    setFormData((prevData) => ({
      ...prevData,
      alunosMonitores: alunos,
    }));
  };

  return (
    <FormContext.Provider
      value={{
        formData,
        saveDraft,
        handleChange,
        handleOdsChange,
        handleCursoChanged,
        handleRoomDataChange,
        handleSaveAlunoMonitor,
        fillOutFormData,
        eventTypes,
        odsTypes,
        resourcesTypes,
        targetPublicTypes,
        roomTypes,
        loading,
        eventId,
        setLoading,
      }}
    >
      {children}
    </FormContext.Provider>
  );
};

export const useFormContext = () => {
  return useContext(FormContext);
};
