import React, { useState, useEffect, useRef } from "react";
import "./Organizer.scss";
import AvatarImage from "../../images/man.png";
import BackButton from "../../components/BackButton";
import { useLocation, useNavigate } from "react-router";
import apiService from "../../services/client";
import { isAllowedOrganizerEmail } from "../../utils/emailPolicy";
import { logoutNoticeFrom } from "../../utils/logoutNotice";
import { WAKING_MESSAGE } from "../../utils/wakingMessage";

function Organizer() {
  const [email, setEmail] = useState(() => localStorage.getItem("email") || "");
  const [errors, setErro] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const emailRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();
  const logoutNotice = logoutNoticeFrom(location.state);

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

  // A validation error moves the focus to the invalid field, so keyboard and
  // screen-reader users land where the correction is made (the alert is read via aria-describedby).
  const invalidEmail = (message) => {
    setErro(message);
    emailRef.current?.focus();
    return false;
  };

  const validEmail = () => {
    if (!email.trim()) return invalidEmail("O campo e-mail é obrigatório.");
    if (!isAllowedOrganizerEmail(email, import.meta.env.VITE_AUTH_EMAIL_ALLOWLIST))
      return invalidEmail("O campo e-mail está fora do formato permitido.");
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
        <h1 className="visually-hidden">Organizador</h1>
        <form onSubmit={sendEmail} noValidate>
        <div className="row">
          <div className="col-md-12 text-center">
            <img
              className="img-man mb-2"
              src={AvatarImage}
              style={{ width: "200px" }}
              alt=""
            />
            <label htmlFor="organizer-email" className="visually-hidden">
              E-mail institucional
            </label>
            <input
              id="organizer-email"
              ref={emailRef}
              type="email"
              name="email"
              inputMode="email"
              autoComplete="email"
              required
              placeholder="Digite seu email@udf.edu.br"
              value={email}
              onChange={handleChange}
              className="form-control"
              aria-invalid={errors ? "true" : undefined}
              aria-describedby={errors ? "organizer-email-error" : undefined}
            />
            {errors && (
              <p id="organizer-email-error" role="alert" className="form-error">
                {errors}
              </p>
            )}
            {/* Always mounted: a live region is announced when its text changes, not when it appears. */}
            <div role="status" aria-live="polite" className="form-notice">
              {notice}
            </div>
            {logoutNotice && <p role="status" className="form-notice">{logoutNotice}</p>}
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
