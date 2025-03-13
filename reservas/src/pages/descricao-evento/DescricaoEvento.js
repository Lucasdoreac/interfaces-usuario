import React, { useState, useCallback, useRef } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import debounce from "lodash.debounce";
import "./DescricaoEvento.scss";
import { useNavigate } from "react-router-dom";
import { useFormContext } from "../../context/FormContext";
import apiService from "../../services/client";
import TwoButtons from "../../components/TwoButtons";

const DescricaoEvento = () => {
  const navigate = useNavigate();
  const { formData, handleChange, handleSaveDraft, handleCursoChanged } = useFormContext();
  
  const [errors, setErrors] = useState({});
  const [searchResults, setSearchResults] = useState([]);
  const [courseSelected, setCourseSelected] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);

  // Cache para pesquisas já realizadas
  const searchCache = useRef({});

  // Função de busca debounced
  const debouncedSearch = useCallback(
    debounce(async (q) => {
      if (searchCache.current[q]) {
        setSearchResults(searchCache.current[q]);
        return;
      }
      setLoading(true);
      const result = await apiService.searchCourses(q);
      const courses = result?.courses || [];
      searchCache.current[q] = courses;
      setSearchResults(courses);
      setLoading(false);
    }, 2000),
    []
  );

  const handleQueryChange = (e) => {
    const value = e.target.value;
    setQuery(value);
    if (value) {
      debouncedSearch(value);
    } else {
      setSearchResults([]);
    }
  };

  const validateEventDescription = () => {
    const newErrors = {};
    if (!formData.descricaoEvento?.trim()) newErrors.descricaoEvento = "Campo obrigatório.";
    if (!formData.courseId) newErrors.curso = "Campo obrigatório.";
    if (!formData.publicoAlvo?.length) newErrors.publicoAlvo = "Selecione pelo menos um público alvo.";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handler para selecionar curso
  const handleCourseSelect = (e) => {
    const selectedName = e.target.value;
    const selectedCourse = searchResults.find((curso) => curso.name === selectedName);
    if (selectedCourse) {
      setCourseSelected(selectedName);
      handleCursoChanged(selectedName, selectedCourse.id);
    }
  };

  // Handler para checkboxes (público alvo e recursos necessários)
  const handleCheckboxChange = (name, value) => {
    const currentValues = formData[name] || [];
    const updatedValues = currentValues.includes(value)
      ? currentValues.filter((item) => item !== value)
      : [...currentValues, value];
    handleChange({ target: { name, value: updatedValues } });
  };

  const handleNext = () => {
    if (validateEventDescription()) {
      handleSaveDraft();
      navigate("/local-evento");
    }
  };

  const renderError = (field) => errors[field] && <span className="error">{errors[field]}</span>;

  return (
    <form>
      <div className="card">
        <div className="card-header">
          <span onClick={() => navigate("/dados-pessoais")}>
            <AiOutlineLeft size="20px" color="white" style={{ marginRight: 10 }} />
          </span>
          <h5>X Cancelar</h5>
        </div>

        <div className="card-body">
          <h4>Novo Evento</h4>
          
          <div className="form-group mt-3">
            <label htmlFor="descricaoEvento">Descrição do evento/ Objetivos</label>
            <textarea
              rows="2"
              className="form-control"
              id="descricaoEvento"
              name="descricaoEvento"
              value={formData.descricaoEvento || ""}
              onChange={handleChange}
            />
            {renderError("descricaoEvento")}
          </div>

          <div className="form-group mt-3">
            <p>Curso Vinculado</p>
            <div className="curso-search">
              <div>
                <label htmlFor="curso-search">Pesquisar/Filtrar</label>
                <input
                  type="text"
                  id="curso-search"
                  className="form-control"
                  placeholder="Buscar curso..."
                  value={query}
                  onChange={handleQueryChange}
                />
              </div>
              <div>
                <label htmlFor="curso">
                  {searchResults.length} cursos encontrados
                </label>
                {loading ? (
                  <p>Pesquisando cursos...</p>
                ) : (
                  <select
                    id="curso"
                    name="curso"
                    value={formData.courseName || courseSelected}
                    onChange={handleCourseSelect}
                    className="form-control"
                  >
                    <option value="" disabled>
                      Nome curso
                    </option>
                    {searchResults.map((curso) => (
                      <option value={curso.name} key={curso.id}>
                        {curso.name}
                      </option>
                    ))}
                  </select>
                )}
                {renderError("curso")}
              </div>
            </div>
          </div>

          <div className="form-group mt-3">
            <label>Público alvo</label>
            {[
              { id: "alunosUDF", label: "Alunos UDF" },
              { id: "professores", label: "Professores" },
              { id: "publicoExterno", label: "Público Externo" },
            ].map(({ id, label }) => (
              <div className="form-check" key={id}>
                <input
                  className="form-check-input"
                  type="checkbox"
                  name="publicoAlvo"
                  id={id}
                  value={id}
                  checked={formData.publicoAlvo?.includes(id) || false}
                  onChange={() => handleCheckboxChange("publicoAlvo", id)}
                />
                <label className="form-check-label" htmlFor={id}>
                  {label}
                </label>
              </div>
            ))}
            {renderError("publicoAlvo")}
          </div>

          <div className="form-group mt-3">
            <label>Recursos Necessários</label>
            {[
              { id: "humanas", label: "Humanas" },
              { id: "tecnologias", label: "Tecnologias" },
              { id: "servicos", label: "Serviços" },
              { id: "materiais", label: "Materiais" },
            ].map(({ id, label }) => (
              <div className="form-check" key={id}>
                <input
                  className="form-check-input"
                  type="checkbox"
                  name="recursosNecessarios"
                  id={id}
                  value={id}
                  checked={formData.recursosNecessarios?.includes(id) || false}
                  onChange={() => handleCheckboxChange("recursosNecessarios", id)}
                />
                <label className="form-check-label" htmlFor={id}>
                  {label}
                </label>
              </div>
            ))}
          </div>

          <TwoButtons handleSaveDraft={handleSaveDraft} handleNext={handleNext} />
        </div>
      </div>
    </form>
  );
};

export default DescricaoEvento;
