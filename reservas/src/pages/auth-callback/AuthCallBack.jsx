import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useLocation, useNavigate } from "react-router";
import EnvImage from "../../images/email.png";
import { AiOutlineLeft } from "react-icons/ai";
import apiService from "../../services/client";
import Loading from "../../components/Loading";

const AuthCallBack = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [emailState, setEmail] = useState("");

  const queryParams = useMemo(
    () => new URLSearchParams(location.search),
    [location.search]
  );

  const emailConfirmado = useCallback(async () => {
    // Start the loading process
    setLoading(true);

    await new Promise((resolve) => setTimeout(resolve, 2000));

    const linkToken = queryParams.get("hash");
    const email = queryParams.get("email") || localStorage.getItem("userEmail");
    if (!email) {
      localStorage.clear();
      return navigate("/organizer");
    }

    setEmail(email); // Set email state early

    // A session from an earlier visit (same address) keeps working on reload.
    const stored = localStorage.getItem("token");
    if (stored && localStorage.getItem("userEmail") === email &&
        (await apiService.validateToken(stored, email))) {
      return navigate("/event/mine");
    }

    if (linkToken) {
      // The link is single use: trade it for a session token.
      const session = await apiService.exchangeToken(linkToken, email);
      if (session) {
        localStorage.clear();
        localStorage.setItem("userEmail", email);
        localStorage.setItem("token", session);
        return navigate("/event/mine");
      }
      return navigate("/access-denied");
    }

    setLoading(false);
  }, [queryParams, navigate]);

  useEffect(() => {
    emailConfirmado();
  }, [emailConfirmado]);

  return (
    <div>
      <div className="card-header">
        <div className="d-flex justify-content-start">
          <span onClick={() => navigate("/organizer")}>
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
        {loading ? (
          <div className="d-flex justify-content-center align-items-center">
            <Loading />
          </div>
        ) : (
          <div className="row">
            <div className="col-md-12 text-center">
              <img
                className="img-man mb-2"
                src={EnvImage}
                style={{ width: "200px", backgroundColor: "transparent" }}
                alt="man avatar"
              />
              <p>
                Clique no botão de autorizar que enviamos para{" "}
                <b>{emailState}</b>
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
        )}
      </div>
    </div>
  );
};

export default AuthCallBack;
