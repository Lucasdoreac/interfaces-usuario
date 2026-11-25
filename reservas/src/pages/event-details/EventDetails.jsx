import React, { useState, useCallback, useRef, useEffect } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import debounce from "lodash.debounce";
import { useNavigate } from "react-router";
import "./EventDetails.scss";
import { showCourseSearch } from "../../utils/courseField";
import { useFormContext } from "../../context/FormContext";
import apiService from "../../services/client";
import TwoButtons from "../../components/TwoButtons";

const EventDetails = () => {
  const navigate = useNavigate();

  const {
    formData,
    handleChange,
    saveDraft,
    handleCursoChanged,
    loading,
    resourcesTypes,
    targetPublicTypes,
    eventId,
  } = useFormContext();

  const [errors, setErrors] = useState({});
  const [searchResults, setSearchResults] = useState([]);
  const [courseSelected, setCourseSelected] = useState("");
  const [query, setQuery] = useState(formData.courseName || "");
  const [localLoading, setLocalLoading] = useState(false);
  // Toggle whether user is editing the course field
  const [editingCourse, setEditingCourse] = useState(false);
  const isEditingCourse = showCourseSearch({ courseId: formData.courseId, editing: editingCourse });

  // Cache for already performed searches
  const searchCache = useRef({});

  // Debounced search function for courses
  const debouncedSearch = useCallback(() => {
    const debouncedFn = debounce(async (q) => {
      if (searchCache.current[q]) {
        setSearchResults(searchCache.current[q]);
        return;
      }
      setLocalLoading(true);
      setCourseSelected("");
      const result = await apiService.searchCourses(q);
      const courses = result?.courses || [];
      searchCache.current[q] = courses;
      setSearchResults(courses);
      setLocalLoading(false);
    }, 2000);
    return debouncedFn;
  }, [searchCache])();

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
    if (!formData.descricaoEvento?.trim())
      newErrors.descricaoEvento = "Campo obrigatório.";
    if (!formData.courseId) newErrors.curso = "Campo obrigatório.";
    if (!formData.publicoAlvo?.length)
      newErrors.publicoAlvo = "Selecione pelo menos um público alvo.";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleCourseSelect = (e) => {
    const selectedName = e.target.value;
    const selectedCourse = searchResults.find(
      (curso) => curso.name === selectedName
    );
    if (selectedCourse) {
      setCourseSelected(selectedCourse.name);
      handleCursoChanged(selectedCourse.name, selectedCourse.id);
      // When a new course is selected, exit editing mode.
      setEditingCourse(false);
    }
  };

  // If courseId exists but courseName is not set, fetch it and update formData.
  useEffect(() => {
    const fetchCourseIfNeeded = async () => {
      if (formData.courseId && !formData.courseName) {
        try {
          const course = await apiService.getCourseById(formData.courseId);
          if (course) {
            handleCursoChanged(course.name, course.id);
            setQuery(course.name);
          }
        } catch (error) {
          console.error("Error fetching course data:", error);
        }
      }
    };
    fetchCourseIfNeeded();
  }, [formData.courseId, formData.courseName, handleCursoChanged]);

  const handleNext = async () => {
    if (validateEventDescription()) {
      const eventId = await saveDraft();
      if (eventId) {
        navigate(`/event/logistics?eventId=${eventId}`);
        return;
      }
      navigate("/event/basic-info");
      return;
    }
  };

  const renderError = (field) =>
    errors[field] && <span className="error">{errors[field]}</span>;

  return (
    <form onSubmit={(e) => e.preventDefault()}>
      <div className="card">
        <div className="card-header">
          <span
            onClick={() => navigate(`/event/basic-info?eventId=${eventId}`)}
          >
            <AiOutlineLeft
              size="20px"
              color="white"
              style={{ marginRight: 10 }}
            />
          </span>
        </div>

        <div className="card-body">
          {loading ? (
            <p>Carregando dados do evento...</p>
          ) : (
            <>
              <h1 className="h4">Novo Evento</h1>

              <div className="form-group mt-3">
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

              <div className="form-group mt-3">
                <p>Curso Vinculado</p>
                {isEditingCourse ? (
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
                      {localLoading ? (
                        <p>Pesquisando cursos...</p>
                      ) : (
                        <select
                          id="curso"
                          name="curso"
                          value={courseSelected || formData.courseName || ""}
                          onChange={handleCourseSelect}
                          disabled={localLoading}
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
                ) : (
                  <div>
                    <input
                      type="text"
                      className="form-control"
                      value={formData.courseName || ""}
                      disabled
                    />
                    <button
                      type="button"
                      className="btn btn-warning btn-secondary"
                      onClick={() => {
                        // Reset course selection in context and local state.
                        handleCursoChanged("", null);
                        setCourseSelected("");
                        setQuery("");
                        setSearchResults([]);
                        setEditingCourse(true);
                      }}
                      style={{ marginTop: "10px" }}
                    >
                      Alterar curso
                    </button>
                  </div>
                )}
              </div>

              <div className="form-group mt-3">
                <label>Público alvo</label>
                {targetPublicTypes.map(({ id, label }) => (
                  <div className="form-check" key={id}>
                    <input
                      className="form-check-input"
                      type="checkbox"
                      name="publicoAlvo"
                      id={id}
                      value={id}
                      checked={formData.publicoAlvo?.includes(id) || false}
                      onChange={() => {
                        const currentValues = formData.publicoAlvo || [];
                        const updatedValues = currentValues.includes(id)
                          ? currentValues.filter((item) => item !== id)
                          : [...currentValues, id];
                        handleChange({
                          target: { name: "publicoAlvo", value: updatedValues },
                        });
                      }}
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
                {resourcesTypes.map(({ id, label }) => (
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
                      onChange={() => {
                        const currentValues =
                          formData.recursosNecessarios || [];
                        const updatedValues = currentValues.includes(id)
                          ? currentValues.filter((item) => item !== id)
                          : [...currentValues, id];
                        handleChange({
                          target: {
                            name: "recursosNecessarios",
                            value: updatedValues,
                          },
                        });
                      }}
                    />
                    <label className="form-check-label" htmlFor={id}>
                      {label}
                    </label>
                  </div>
                ))}
              </div>

              <TwoButtons saveDraft={saveDraft} handleNext={handleNext} />
            </>
          )}
        </div>
      </div>
    </form>
  );
};

export default EventDetails;
