import React, { useState, useEffect } from "react";
import { Navigate, useNavigate } from "react-router";
import apiService from "../src/services/client";
import Loading from "./components/Loading";
import { sessionEndedByStorageEvent } from "./utils/session";

const LOCAL_STORAGE_KEYS = {
  TOKEN: "token",
  EMAIL: "userEmail",
};

const PrivateRoute = ({ element: Component, ...rest }) => {
  const [isAuthorized, setIsAuthorized] = useState(null);
  const navigate = useNavigate();
  const token = localStorage.getItem(LOCAL_STORAGE_KEYS.TOKEN);
  const email = localStorage.getItem(LOCAL_STORAGE_KEYS.EMAIL);

  useEffect(() => {
    const onStorage = (event) => {
      if (!sessionEndedByStorageEvent(event, globalThis.localStorage)) return;
      setIsAuthorized(false);
      navigate("/organizer", { replace: true });
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [navigate]);

  useEffect(() => {
    let active = true;
    const validateUserToken = async () => {
      if (token && email) {
        const isValid = await apiService.validateToken(token, email);
        if (active) {
          setIsAuthorized(isValid && localStorage.getItem(LOCAL_STORAGE_KEYS.TOKEN) === token
            && localStorage.getItem(LOCAL_STORAGE_KEYS.EMAIL) === email);
        }
      } else {
        if (active) setIsAuthorized(false);
      }
    };
    validateUserToken();
    return () => { active = false; };
  }, [token, email]);

  if (isAuthorized === null) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <Loading />
      </div>
    );
  }

  return isAuthorized ? (
    <Component {...rest} />
  ) : (
    <Navigate to="/access-denied" />
  );
};

export default PrivateRoute;
