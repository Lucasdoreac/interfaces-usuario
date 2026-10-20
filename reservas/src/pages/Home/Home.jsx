import React, { useEffect } from "react";
import "./Home.scss";
import AvatarImage from "../../images/man.png";
import { useNavigate } from "react-router"; // Importar useNavigate para navegação
import apiService from "../../services/client";

const Home = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const checkToken = async () => {
      const userEmail = localStorage.getItem("userEmail");
      const token = localStorage.getItem("token");

      if (userEmail && token) {
        const valid = await apiService.validateToken(token, userEmail);
        if (valid) {
          navigate("/event/mine");
        }
      }
    };

    checkToken();
  }, [navigate]);

  return (
    <div>
      <div className="card-header">
        <div className="row mb-4">
          <div className="col-md-3">{/* Espaço vazio */}</div>
        </div>
      </div>
      <div className="card-body">
        <div className="row">
          <div className="col-md-12 text-center">
            <img
              className="img-man"
              src={AvatarImage}
              style={{ width: "200px" }}
              alt="man avatar"
            />
            <div className="d-grid gap-3 d-sm-flex justify-content-sm-center mt-4">
              <button
                type="button"
                className="btn btn-outline-primary btn-lg"
                onClick={() => navigate("/espacos")}
              >
                ESPAÇOS E ORIENTAÇÕES
              </button>
              <button
                type="button"
                className="btn btn-primary btn-lg"
                onClick={() => navigate("/organizer")}
              >
                ORGANIZADOR
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Home;
