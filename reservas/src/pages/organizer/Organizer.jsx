import React, { useState, useEffect } from "react";
import "./Organizer.scss";
import AvatarImage from "../../images/man.png";
import BackButton from "../../components/BackButton";
import { useNavigate } from "react-router";
import apiService from "../../services/client";
import { isAllowedOrganizerEmail } from "../../utils/emailPolicy";
import { clearAuthStorage } from "../../utils/authStorage";

function Organizer() {
  const [email, setEmail] = useState(() => localStorage.getItem("email") || "");
  const [errors, setErro] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    setEmail(e.target.value);
  };

  const sendEmail = async (event) => {
    event.preventDefault();
    if (validEmail()) {
      const normalizedEmail = email.trim();
      setLoading(true);
      clearAuthStorage(localStorage);
      localStorage.setItem("email", normalizedEmail);
      const result = await apiService.postAuthMail(normalizedEmail);
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
    if (!isAllowedOrganizerEmail(email)) {
      setErro("O campo e-mail está fora do formato permitido.");
      return false;
    }
    return true;
  };

  return (
    <div>
      <div className="card-header">
        <div className="d-flex justify-content-start">
          <BackButton onClick={() => navigate("/")} />
        </div>
      </div>
      <div className="card-body" aria-busy={loading}>
        <form onSubmit={sendEmail} noValidate>
        <div className="row">
          <div className="col-md-12 text-center">
            <img
              className="img-man mb-2"
              src={AvatarImage}
              style={{ width: "200px" }}
              alt="man avatar"
            />
            <label htmlFor="organizer-email" className="visually-hidden">E-mail institucional</label>
            <input
              id="organizer-email"
              type="email"
              inputMode="email"
              autoComplete="email"
              name="email"
              placeholder="Digite seu email@udf.edu.br"
              value={email}
              onChange={handleChange}
              className="form-control"
              aria-invalid={errors ? "true" : undefined}
              aria-describedby={errors ? "organizer-email-error" : undefined}
            />
            {errors && <p id="organizer-email-error" role="alert" className="form-error">{errors}</p>}
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
