import React, { createContext, useContext, useState } from "react";

const FormContext = createContext();

export const FormProvider = ({ children }) => {
  const [formData, setFormData] = useState({
    nomeProfessor: localStorage.getItem("userEmail") || "",
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prevData) => ({ ...prevData, [name]: value }));
  };

  const handleSaveDraft = () => {
    // Save form data to local storage or send to a draft endpoint
    localStorage.setItem("eventDraft", JSON.stringify(formData));
    alert("Rascunho salvo com sucesso!");
  };

  return (
    <FormContext.Provider value={{ formData, handleChange, handleSaveDraft }}>
      {children}
    </FormContext.Provider>
  );
};

export const useFormContext = () => {
  return useContext(FormContext);
};
