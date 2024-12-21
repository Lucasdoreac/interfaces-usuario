import React, { useState, useCallback } from "react";
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

  // Memoized search cache
  const searchCache = React.useRef({});

  // Debounced search function
  const debouncedSearch = useCallback(
    debounce(async (query) => {
      if (searchCache.current[query]) {
        setSearchResults(searchCache.current[query]);
        return;
      }
      setLoading(true);
      const result = await apiService.searchCourses(query);
      if (result?.courses) {
        searchCache.current[query] = result.courses;
        setSearchResults(result.courses);
      } else {
        setSearchResults([]);
      }
      setLoading(false);
    }, 2000),
    []
  );

  // Handle query input
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

    if (!formData.descricaoEvento?.trim()) {
      newErrors.descricaoEvento = "Campo obrigatório.";
    }
    if (!formData.courseId) {
      newErrors.curso = "Campo obrigatório.";
    }
    if (!formData.publicoAlvo?.length) {
      newErrors.publicoAlvo = "Selecione pelo menos um público alvo.";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const teste = (e) => {
    const selectedCourseName = e.target.value;
    const selectedCourse = searchResults.find((curso) => curso.name === selectedCourseName);
  
    if (selectedCourse) {
      setCourseSelected(selectedCourseName);
      handleCursoChanged(selectedCourseName, selectedCourse.id);
    }
  };

  const handleNext = () => {
    if (validateEventDescription()) {
      handleSaveDraft();
      navigate("/local-evento");
    }
  };

  const handleCheckboxChange = (name, value) => {
    const currentValues = formData[name] || [];
    const updatedValues = currentValues.includes(value)
      ? currentValues.filter((item) => item !== value)
      : [...currentValues, value];
    handleChange({ target: { name, value: updatedValues } });
  };

  const renderError = (field) =>
    errors[field] && <span style={{ color: "red" }}>{errors[field]}</span>;

  return (
    <form>
      <div>
        <div className="card-header">
          <div className="d-flex justify-content-start">
            <span onClick={() => navigate("/dados-pessoais")}>
              <AiOutlineLeft
                style={{ margin: "0 10px 0 0" }}
                size="20px"
                color="white"
              />
            </span>
            <h5>X Cancelar</h5>
          </div>
        </div>

        <div className="card-body">
          <div className="row">
            <div className="col-md-12">
              <h4>Novo Evento</h4>
            </div>
          </div>

          <div className="row mt-3">
            <div className="col">
              <label htmlFor="descricaoEvento">
                Descrição do evento/ Objetivos
              </label>
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
          </div>

          <div className="row mt-3">
            <p>Curso Vinculado</p>
            <div
              className="row"
              style={{ borderLeft: "2px solid #f0f0f0", marginLeft: 5 }}
            >
              <div className="col-md-6 col-sm-12">
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
              <div className="col-md-6 col-sm-12">
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
                    onChange={teste}
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

          <div className="row mt-3">
            <div className="col">
              <label>Público alvo</label>
              {[
                { id: "alunosUDF", label: "Alunos UDF" },
                { id: "professores", label: "Professores" },
                { id: "publicoExterno", label: "Público externo" },
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
          </div>

          <div className="row mt-3">
            <div className="col">
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
                    checked={
                      formData.recursosNecessarios?.includes(id) || false
                    }
                    onChange={() =>
                      handleCheckboxChange("recursosNecessarios", id)
                    }
                  />
                  <label className="form-check-label" htmlFor={id}>
                    {label}
                  </label>
                </div>
              ))}
            </div>
          </div>

          <TwoButtons
            handleSaveDraft={handleSaveDraft}
            handleNext={handleNext}
          />
        </div>
      </div>
    </form>
  );
};

export default DescricaoEvento;
