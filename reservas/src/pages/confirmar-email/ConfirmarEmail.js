import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import EnvImage from "../../images/email.png";
import { AiOutlineLeft } from "react-icons/ai";
import "./ConfirmarEmail.scss";
import apiService from "../../services/client";

const ConfirmarEmail = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");

  const queryParams = useMemo(
    () => new URLSearchParams(location.search),
    [location.search]
  );

  const getUserData = useCallback(() => {
    const token = queryParams.get("hash") || localStorage.getItem("token");
    const email = queryParams.get("email") || localStorage.getItem("userEmail");
    return { token, email };
  }, [queryParams]);

  const emailConfirmado = useCallback(async () => {
    const { token, email } = getUserData();

    if (email) {
      if (token && (await apiService.validateToken(token, email))) {
        localStorage.clear();
        localStorage.setItem("userEmail", email);
        localStorage.setItem("token", token);
        return navigate("/dados-pessoais");
      }
      setEmail(email);
    } else {
      return navigate("/acesso-negado");
    }
  }, [getUserData, navigate]);

  useEffect(() => {
    emailConfirmado();
  }, [emailConfirmado]);

  return (
    <div>
      <div className="card-header">
        <div className="d-flex justify-content-start">
          <span onClick={() => navigate("/organizador")}>
            <AiOutlineLeft
              style={{ margin: "0px 10px 0px 0px" }}
              size="20px"
              color="white"
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
              src={EnvImage}
              style={{ width: "200px", backgroundColor: "transparent" }}
              alt="man avatar"
            />
            <p>
              Clique no link do e-mail que enviamos para <b>{email}</b>
            </p>
            <div className="mt-4">
              <button
                type="button"
                className="btn btn-primary btn-lg"
                onClick={emailConfirmado}
              >
                <b>Já Confirmei!</b>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfirmarEmail;
