import React, { createContext, useContext, useState } from "react";

const FormContext = createContext();

export const FormProvider = ({ children }) => {
  const [formData, setFormData] = useState({
    nomeProfessor: localStorage.getItem("userEmail") || "",
    alunosMonitores: [],
  });

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

  const handleRoomDataChange = (roomId, reservationDate) => {
    setFormData((prevData) => ({
      ...prevData,
      roomId,
      reservationDate,
    }));
  };

  const handleSaveDraft = () => {
    localStorage.setItem("eventDraft", JSON.stringify(formData));
    alert("Rascunho salvo com sucesso!");
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
        handleChange,
        handleOdsChange,
        handleCursoChanged,
        handleRoomDataChange,
        handleSaveDraft,
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
