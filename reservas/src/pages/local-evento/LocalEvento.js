import React, { useState } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate } from "react-router-dom";
import { useFormContext } from "../../context/FormContext";
import apiService from "../../services/client";

const LocalEvento = () => {
  const navigate = useNavigate();
  const { formData, handleChange, handleSaveDraft, handleSaveAlunoMonitor } = useFormContext();
  const [alunosMonitores, setAlunosMonitores] = useState(formData.alunosMonitores || []);
  const [errors, setErrors] = useState({});
  const [logoPreview, setLogoPreview] = useState(null);

  const handleAddAluno = () => {
    const updatedAlunos = [...alunosMonitores, ""];
    setAlunosMonitores(updatedAlunos);
    handleSaveAlunoMonitor(updatedAlunos);
  };

  const handleRemoveAluno = (index) => {
    const updatedAlunos = alunosMonitores.filter((_, i) => i !== index);
    setAlunosMonitores(updatedAlunos);
    handleSaveAlunoMonitor(updatedAlunos);
  };

  const handleAlunoChange = (index, value) => {
    const updatedAlunos = alunosMonitores.map((aluno, i) => (i === index ? value : aluno));
    setAlunosMonitores(updatedAlunos);
    handleSaveAlunoMonitor(updatedAlunos);
  };

  const handleLogoUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = () => setLogoPreview(reader.result);
      reader.readAsDataURL(file);
    }
    handleChange({ target: { name: "logo", value: file } });
  };

  const validateForm = () => {
    const newErrors = {};
    if (!formData.numeroParticipantes?.trim() || formData.numeroParticipantes <= 0)
      newErrors.numeroParticipantes = "Número de participantes é obrigatório.";
    if (!formData.espacos?.trim())
      newErrors.espacos = "Selecione um espaço necessário.";
    if (formData.trilha === "sim" && !formData.trilhaDesc?.trim())
      newErrors.trilhaDesc = "Descrição da trilha empreendedora é obrigatória.";
    if (formData.projeto === "sim" && !formData.projetoDesc?.trim())
      newErrors.projetoDesc = "Descrição do projeto de extensão é obrigatória.";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = async () => {
    if (validateForm()) {
      try {
        const response = await apiService.submitForm(formData);
        console.log("Form submitted", response);
        navigate("/evento-confirmacao");
      } catch (error) {
        console.error("Error submitting:", error);
      }
    }
  };

  const renderError = (field) => errors[field] && <span className="error">{errors[field]}</span>;

  return (
    <form>
      <div className="card">
        <div className="card-header">
          <span onClick={() => navigate("/descricao-evento")}>
            <AiOutlineLeft size="20px" color="white" style={{ marginRight: 10 }} />
          </span>
        </div>

        <div className="card-body">
          <h4>Novo Evento</h4>
          
          <div className="form-group mt-3">
            <label htmlFor="numeroParticipantes">Número de participantes</label>
            <input
              type="number"
              className="form-control"
              min="0"
              max="100"
              id="numeroParticipantes"
              name="numeroParticipantes"
              value={formData.numeroParticipantes || ""}
              onChange={handleChange}
              style={{ width: 200 }}
            />
            {renderError("numeroParticipantes")}
          </div>

          <div className="form-group mt-3">
            <label htmlFor="espacos">Espaço Necessário</label>
            {["online", "auditorio", "hall", "salaAula", "laboratorioInfo"].map((espaco) => (
              <div className="form-check" key={espaco}>
                <input
                  className="form-check-input"
                  type="radio"
                  name="espacos"
                  id={espaco}
                  value={espaco}
                  checked={formData.espacos === espaco}
                  onChange={handleChange}
                />
                <label className="form-check-label" htmlFor={espaco}>
                  {espaco.charAt(0).toUpperCase() + espaco.slice(1).replace(/([A-Z])/g, " $1")}
                </label>
              </div>
            ))}
            {renderError("espacos")}
          </div>

          <div className="row mt-3">
            <div className="col-5">
              <label htmlFor="trilha">Trilha empreendedora</label>
              <select
                id="trilha"
                name="trilha"
                value={formData.trilha || "nao"}
                onChange={handleChange}
                className="form-control"
              >
                <option value="nao">Não</option>
                <option value="sim">Sim</option>
              </select>
            </div>
            <div className="col-7">
              <label htmlFor="trilhaDesc">Se sim, digite aqui</label>
              <input
                type="text"
                className="form-control"
                id="trilhaDesc"
                name="trilhaDesc"
                value={formData.trilhaDesc || ""}
                onChange={handleChange}
              />
              {renderError("trilhaDesc")}
            </div>
          </div>

          <div className="row mt-3">
            <div className="col-5">
              <label htmlFor="projeto">Projeto Extensão</label>
              <select
                id="projeto"
                name="projeto"
                value={formData.projeto || "nao"}
                onChange={handleChange}
                className="form-control"
              >
                <option value="nao">Não</option>
                <option value="sim">Sim</option>
              </select>
            </div>
            <div className="col-7">
              <label htmlFor="projetoDesc">Se sim, digite aqui</label>
              <input
                type="text"
                className="form-control"
                id="projetoDesc"
                name="projetoDesc"
                value={formData.projetoDesc || ""}
                onChange={handleChange}
              />
              {renderError("projetoDesc")}
            </div>
          </div>

          <div className="form-group mt-3">
            <label>Alunos Monitores</label>
            {alunosMonitores.map((aluno, index) => (
              <div className="input-group mb-2" key={index}>
                <input
                  type="text"
                  className="form-control"
                  value={aluno}
                  onChange={(e) => handleAlunoChange(index, e.target.value)}
                />
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => handleRemoveAluno(index)}
                >
                  Remover
                </button>
              </div>
            ))}
            <button type="button" className="btn btn-outline-primary" onClick={handleAddAluno}>
              Adicionar Aluno
            </button>
          </div>

          <div className="form-group mt-3">
            <label htmlFor="logo">Logo do Evento</label>
            <input type="file" className="form-control" id="logo" name="logo" onChange={handleLogoUpload} />
            {logoPreview && (
              <img src={logoPreview} alt="Logo Preview" style={{ marginTop: "10px", maxWidth: "200px" }} />
            )}
          </div>

          <div className="form-group mt-3">
            <button type="button" className="btn btn-outline-secondary" onClick={handleSaveDraft}>
              Salvar Rascunho
            </button>
            <button type="button" className="btn btn-primary" onClick={handleNext}>
              Enviar para Coordenação
            </button>
          </div>
        </div>
      </div>
    </form>
  );
};

export default LocalEvento;
