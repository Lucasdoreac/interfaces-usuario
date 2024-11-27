import React, { useState } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import "./DescricaoEvento.scss";
import { useNavigate } from "react-router-dom";
import { useFormContext } from "../../context/FormContext";

const DescricaoEvento = () => {
  const navigate = useNavigate();
  const { formData, handleChange } = useFormContext();
  const [erros, setErros] = useState({});

  const listaCurso = [
    "Ciência da Computação",
    "Sistemas da Informação",
    "Engenharia Civil",
  ];

  const validacaoDescricaoEvento = () => {
    const erro = {};
    if (!formData.linkEvento?.trim()) {
      erro.linkEvento = "Campo obrigatório.";
      setErros(erro);
      return false;
    }
    if (!formData.descricaoEvento?.trim()) {
      erro.descricaoEvento = "Campo obrigatório.";
      setErros(erro);
      return false;
    }
    if (!formData.curso?.trim()) {
      erro.curso = "Campo obrigatório.";
      setErros(erro);
      return false;
    }
    if (!formData.publicoAlvoRadio?.trim()) {
      erro.publicoAlvoRadio = "Campo obrigatório.";
      setErros(erro);
      return false;
    }
    if (!formData.recursosNecessariosRadio?.trim()) {
      erro.recursosNecessariosRadio = "Campo obrigatório.";
      setErros(erro);
      return false;
    }
    return true;
  };

  const confDescricaoEventos = () => {
    if (validacaoDescricaoEvento()) {
      navigate("/local-evento");
    }
  };

  return (
    <form>
      <div>
        <div className="card-header">
          <div className="d-flex d-flex justify-content-start">
            <span onClick={() => navigate("/dados-pessoais")}>
              <AiOutlineLeft
                style={{ margin: "0px 10px 0px 0px" }}
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

          <div className="row">
            <div className="col">
              <label htmlFor="linkEvento">Link do evento/Inscrições</label>
              <input
                type="text"
                className="form-control"
                id="linkEvento"
                name="linkEvento"
                value={formData.linkEvento || ""}
                onChange={handleChange}
              />
              {erros.linkEvento && (
                <span style={{ color: "red" }}>{erros.linkEvento}</span>
              )}
            </div>
          </div>
          <br />
          <div className="row">
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
              {erros.descricaoEvento && (
                <span style={{ color: "red" }}>{erros.descricaoEvento}</span>
              )}
            </div>
          </div>
          <br />
          <div className="row">
            <div className="col">
              <label htmlFor="curso">Curso Vinculado</label>
              <select
                id="curso"
                name="curso"
                value={formData.curso || ""}
                onChange={handleChange}
                className="form-control"
                style={{ width: 200 }}
              >
                <option value="" disabled>
                  {" "}
                  Nome curso e Código{" "}
                </option>
                {listaCurso.map((curso, index) => (
                  <option value={curso} key={index}>
                    {curso}
                  </option>
                ))}
              </select>
              {erros.curso && (
                <span style={{ color: "red" }}>{erros.curso}</span>
              )}
            </div>
          </div>
          <br />
          <div className="row">
            <div className="col">
              <label htmlFor="publicoAlvo">Público alvo</label>
              <br />
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="radio"
                  name="publicoAlvoRadio"
                  id="alunosUDF"
                  onChange={handleChange}
                  value="alunosUDF"
                  checked={formData.publicoAlvoRadio === "alunosUDF"}
                />
                <label className="form-check-label" htmlFor="alunosUDF">
                  Alunos UDF
                </label>
              </div>
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="radio"
                  name="publicoAlvoRadio"
                  id="professores"
                  onChange={handleChange}
                  value="professores"
                  checked={formData.publicoAlvoRadio === "professores"}
                />
                <label className="form-check-label" htmlFor="professores">
                  Professores
                </label>
              </div>
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="radio"
                  name="publicoAlvoRadio"
                  id="publicoExterno"
                  onChange={handleChange}
                  value="publicoExterno"
                  checked={formData.publicoAlvoRadio === "publicoExterno"}
                />
                <label className="form-check-label" htmlFor="publicoExterno">
                  Público externo
                </label>
              </div>
              {erros.publicoAlvoRadio && (
                <span style={{ color: "red" }}>{erros.publicoAlvoRadio}</span>
              )}
            </div>
          </div>
          <br />
          <div className="row">
            <div className="col">
              <label htmlFor="recursosNecessarios">Recursos Necessários</label>
              <br />
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="radio"
                  name="recursosNecessariosRadio"
                  id="humanas"
                  onChange={handleChange}
                  value="humanas"
                  checked={formData.recursosNecessariosRadio === "humanas"}
                />
                <label className="form-check-label" htmlFor="humanas">
                  Humanas
                </label>
              </div>
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="radio"
                  name="recursosNecessariosRadio"
                  id="tecnologias"
                  onChange={handleChange}
                  value="tecnologias"
                  checked={formData.recursosNecessariosRadio === "tecnologias"}
                />
                <label className="form-check-label" htmlFor="tecnologias">
                  Tecnologias
                </label>
              </div>
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="radio"
                  name="recursosNecessariosRadio"
                  id="servicos"
                  onChange={handleChange}
                  value="servicos"
                  checked={formData.recursosNecessariosRadio === "servicos"}
                />
                <label className="form-check-label" htmlFor="servicos">
                  Serviços
                </label>
              </div>
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="radio"
                  name="recursosNecessariosRadio"
                  id="materias"
                  onChange={handleChange}
                  value="materias"
                  checked={formData.recursosNecessariosRadio === "materias"}
                />
                <label className="form-check-label" htmlFor="materias">
                  Materiais
                </label>
              </div>
              {erros.recursosNecessariosRadio && (
                <span style={{ color: "red" }}>
                  {erros.recursosNecessariosRadio}
                </span>
              )}
            </div>
          </div>
          <br />
          <div className="row">
            <div className="col">
              <input
                type="button"
                className="btn btn-outline-secondary"
                value="Salvar Rascunho"
              />
              <button
                type="button"
                className="btn btn-warning"
                onClick={confDescricaoEventos}
              >
                Próximo
              </button>
            </div>
          </div>
        </div>
      </div>
    </form>
  );
};

export default DescricaoEvento;
