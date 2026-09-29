import React, { useState } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate, useLocation } from "react-router";
import { useFormContext } from "../../context/FormContext";
import TwoButtons from "../../components/TwoButtons";

const EventLogistics = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const eventId = queryParams.get("eventId");

  const { formData, handleChange, saveDraft, handleSaveAlunoMonitor } =
    useFormContext();
  const [alunosMonitores, setAlunosMonitores] = useState(
    formData.alunosMonitores || []
  );
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
    const updatedAlunos = alunosMonitores.map((aluno, i) =>
      i === index ? value : aluno
    );
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

  const handleNext = async () => {
    const savedDraftEventId = await saveDraft();
    if (savedDraftEventId) {
      navigate(`/event/schedule?eventId=${savedDraftEventId}`);
    } else {
      // Handle the error if the draft wasn't saved correctly
      console.error("Draft was not saved correctly.");
    }
  };

  const renderError = (field) =>
    errors[field] && <span className="error">{errors[field]}</span>;

  return (
    <form onSubmit={(e) => e.preventDefault()}>
      <div className="card">
        <div className="card-header">
          {/* Append eventId query parameter if available */}
          <span
            onClick={() =>
              navigate(
                "/event/details" + (eventId ? `?eventId=${eventId}` : "")
              )
            }
          >
            <AiOutlineLeft
              size="20px"
              color="white"
              style={{ marginRight: 10 }}
            />
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
            {[
              "online",
              "auditorio",
              "hall",
              "salaAula",
              "laboratorioInformática",
            ].map((espaco) => (
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
                  {espaco.charAt(0).toUpperCase() +
                    espaco.slice(1).replace(/([A-Z])/g, " $1")}
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
            <button
              type="button"
              className="btn btn-outline-primary"
              onClick={handleAddAluno}
            >
              Adicionar Aluno
            </button>
          </div>

          <div className="form-group mt-3">
            <label htmlFor="logo">Logo do Evento</label>
            <input
              type="file"
              className="form-control"
              id="logo"
              name="logo"
              onChange={handleLogoUpload}
            />
            {logoPreview && (
              <img
                src={logoPreview}
                alt="Logo Preview"
                style={{ marginTop: "10px", maxWidth: "200px" }}
              />
            )}
          </div>

          <TwoButtons saveDraft={saveDraft} handleNext={handleNext} />
        </div>
      </div>
    </form>
  );
};

export default EventLogistics;
