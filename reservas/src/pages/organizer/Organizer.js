import React, { useState } from "react";
import "./Organizer.scss";
import AvatarImage from "../../images/man.png";
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate } from "react-router-dom";
import apiService from "../../services/client";
import { useFormContext } from "../../context/FormContext";

function Organizer() {
  const { formData, handleChange } = useFormContext();
  const email = formData.email || "";
  const [errors, setErro] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const sendEmail = async (event) => {
    event.preventDefault();
    if (validEmail()) {
      setLoading(true);
      localStorage.clear();
      if (apiService.postAuthMail(email))
        navigate("/auth/callback?email=" + email);
      else setErro("Serviço indisponível");
      setLoading(false);
    }
  };

  const validEmail = () => {
    if (!email.trim()) {
      setErro("O campo e-mail é obrigatório.");
      return false;
    }
    if (!/^[a-zA-Z0-9._%+-]+@udf\.edu\.br$/.test(email)) {
      setErro("O campo e-mail está fora do formato permitido.");
      return false;
    }
    return true;
  };

  return (
    <div>
      <div className="card-header">
        <div className="d-flex justify-content-start">
          <span onClick={() => navigate("/")}>
            <AiOutlineLeft
              size="20px"
              color="white"
              style={{ margin: "0px 10px 0px 0px" }}
            />
          </span>
          <h5>Voltar</h5>
        </div>
      </div>
      <div className="card-body">
        <div className="row">
          <div className="col-md-12 text-center">
            <img
              className="img-man mb-2"
              src={AvatarImage}
              style={{ width: "200px" }}
              alt="man avatar"
            />
            <input
              type="email"
              name="email" // importante para atualizar a propriedade correta
              placeholder="Digite seu email@udf.edu.br"
              value={email}
              onChange={handleChange}
              className="form-control"
            />
            {errors && <span style={{ color: "red" }}>{errors}</span>}
            <div className="mt-4">
              <button
                type="submit"
                onClick={sendEmail}
                className="btn btn-primary btn-lg"
                disabled={loading}
              >
                <b>{loading ? "Enviando..." : "Próximo"}</b>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Organizer;
