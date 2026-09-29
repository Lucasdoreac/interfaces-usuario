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

  const getUserData = useCallback(() => {
    const token = queryParams.get("hash") || localStorage.getItem("token");
    const email = queryParams.get("email") || localStorage.getItem("userEmail");
    return { token, email };
  }, [queryParams]);

  const emailConfirmado = useCallback(async () => {
    // Start the loading process
    setLoading(true);

    await new Promise((resolve) => setTimeout(resolve, 2000));

    const { token, email } = getUserData();
    if (!email) {
      localStorage.clear();
      return navigate("/organizer");
    }

    setEmail(email); // Set email state early

    if (token && (await apiService.validateToken(token, email))) {
      localStorage.clear();
      localStorage.setItem("userEmail", email);
      localStorage.setItem("token", token);
      return navigate("/event/mine");
    } else if (!!token) {
      // Token exists but is invalid or expired
      return navigate("/access-denied");
    }

    setLoading(false);
  }, [getUserData, navigate]);

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
