import React, { createContext, useContext, useState, useEffect } from "react";
import apiService from "../services/client";

const FormContext = createContext();

export const FormProvider = ({ children }) => {
  const [formData, setFormData] = useState(() => {
    const saved = localStorage.getItem("formData");
    return saved ? JSON.parse(saved) : {};
  });

  useEffect(() => {
    localStorage.setItem("formData", JSON.stringify(formData));
  }, [formData]);

  const saveDraft = async () => {
    try {
      const existingEventId = localStorage.getItem("eventId");
      const draftId = await apiService.submitEventData(
        formData,
        "draft",
        existingEventId
      );
      localStorage.setItem("eventId", draftId);
      console.log("Saved Draft ID: ", draftId);
    } catch (error) {
      console.error("Erro ao salvar draft:", error);
      return null;
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prevData) => ({ ...prevData, [name]: value }));
  };

  const handleOdsChange = (e) => {
    const { value } = e.target;
    const parts = value.split(" - ");
    const odsId = parts[0];
    const odsName = parts[1]?.split(" (")[0].trim();
    setFormData((prevData) => ({
      ...prevData,
      ods: value,
      odsId,
      odsName,
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
      reservationDate,
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
      }}
    >
      {children}
    </FormContext.Provider>
  );
};

export const useFormContext = () => {
  return useContext(FormContext);
};
