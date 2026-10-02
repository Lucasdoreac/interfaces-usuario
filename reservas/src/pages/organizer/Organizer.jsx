import React, { useState, useEffect } from "react";
import "./Organizer.scss";
import AvatarImage from "../../images/man.png";
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate } from "react-router";
import apiService from "../../services/client";
import { isAllowedOrganizerEmail } from "../../utils/emailPolicy";
import { WAKING_MESSAGE } from "../../utils/wakingMessage";

function Organizer() {
  const [email, setEmail] = useState(() => localStorage.getItem("email") || "");
  const [errors, setErro] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const navigate = useNavigate();

  const handleChange = (e) => {
    setEmail(e.target.value);
  };

  const sendEmail = async (event) => {
    event.preventDefault();
    if (validEmail()) {
      const normalizedEmail = email.trim();
      setLoading(true);
      localStorage.clear();
      localStorage.setItem("email", normalizedEmail);
      setNotice("");
      const stopWaking = apiService.onWaking(() => setNotice(WAKING_MESSAGE));
      const result = await apiService.postAuthMail(normalizedEmail);
      stopWaking();
      setNotice("");
      if (result?.dryRun)
        setErro("Modo de teste ativo: nenhum e-mail foi enviado.");
      else if (result)
        navigate("/auth/callback?email=" + encodeURIComponent(normalizedEmail));
      else setErro("Serviço indisponível");
      setLoading(false);
    }
  };

  const validEmail = () => {
    if (!email.trim()) {
      setErro("O campo e-mail é obrigatório.");
      return false;
    }
    if (!isAllowedOrganizerEmail(email, import.meta.env.VITE_AUTH_EMAIL_ALLOWLIST)) {
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
        <form onSubmit={sendEmail} noValidate>
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
              name="email"
              placeholder="Digite seu email@udf.edu.br"
              value={email}
              onChange={handleChange}
              className="form-control"
            />
            {errors && <span style={{ color: "red" }}>{errors}</span>}
            {notice && <span role="status" style={{ color: "#555" }}>{notice}</span>}
            <div className="mt-4">
              <button
                type="submit"
                className="btn btn-primary btn-lg"
                disabled={loading}
              >
                <b>{loading ? "Enviando..." : "Próximo"}</b>
              </button>
            </div>
          </div>
        </div>
        </form>
      </div>
    </div>
  );
}

export default Organizer;
