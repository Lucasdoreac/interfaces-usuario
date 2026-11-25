import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useLocation, useNavigate } from "react-router";
import EnvImage from "../../images/email.png";
import BackButton from "../../components/BackButton";
import apiService from "../../services/client";
import Loading from "../../components/Loading";
import { resolveCallback, signIn } from "../../utils/callbackFlow";

const AuthCallBack = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [emailState, setEmail] = useState("");
  const [needsClick, setNeedsClick] = useState(false);

  const queryParams = useMemo(
    () => new URLSearchParams(location.search),
    [location.search]
  );

  const checkSession = useCallback(async () => {
    setLoading(true);
    const email = queryParams.get("email") || localStorage.getItem("userEmail");
    const linkToken = queryParams.get("hash");
    if (email) setEmail(email);

    const result = await resolveCallback({ api: apiService, storage: localStorage, email, linkToken });
    if (result.action === "organizer") {
      localStorage.clear();
      return navigate("/organizer");
    }
    if (result.action === "events") return navigate("/event/mine");
    setNeedsClick(result.action === "needs-click");
    setLoading(false);
  }, [queryParams, navigate]);

  // Only the stored session is checked on load; the link is spent on the click below.
  useEffect(() => {
    checkSession();
  }, [checkSession]);

  const enter = async () => {
    setLoading(true);
    const result = await signIn({
      api: apiService,
      storage: localStorage,
      email: emailState,
      linkToken: queryParams.get("hash"),
    });
    if (result.action === "events") return navigate("/event/mine");
    return navigate("/access-denied");
  };

  return (
    <div>
      <div className="card-header">
        <div className="d-flex justify-content-start">
          <BackButton onClick={() => navigate("/organizer")} />
        </div>
      </div>
      <div className="card-body">
        <h1 className="visually-hidden">Entrar</h1>
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
                alt=""
              />
              {needsClick ? (
                <>
                  <p>
                    Entrar como <b>{emailState}</b>
                  </p>
                  <div className="mt-4">
                    <button
                      type="button"
                      className="btn btn-primary btn-lg"
                      onClick={enter}
                    >
                      <b>Entrar</b>
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <p>
                    Clique no botão de autorizar que enviamos para{" "}
                    <b>{emailState}</b>
                  </p>
                  <div className="mt-4">
                    <button
                      type="button"
                      className="btn btn-primary btn-lg"
                      onClick={checkSession}
                    >
                      <b>Já Confirmei!</b>
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuthCallBack;
