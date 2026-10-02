import React, { useState, useEffect } from "react";
import { Navigate } from "react-router";
import apiService from "../src/services/client";
import Loading from "./components/Loading";
import { WAKING_MESSAGE } from "./utils/wakingMessage";

const LOCAL_STORAGE_KEYS = {
  TOKEN: "token",
  EMAIL: "userEmail",
};

const PrivateRoute = ({ element: Component, ...rest }) => {
  const [isAuthorized, setIsAuthorized] = useState(null);
  const [waking, setWaking] = useState(false);
  const token = localStorage.getItem(LOCAL_STORAGE_KEYS.TOKEN);
  const email = localStorage.getItem(LOCAL_STORAGE_KEYS.EMAIL);

  useEffect(() => apiService.onWaking(() => setWaking(true)), []);

  useEffect(() => {
    const validateUserToken = async () => {
      if (token && email) {
        const isValid = await apiService.validateToken(token, email);
        setIsAuthorized(isValid);
      } else {
        setIsAuthorized(false);
      }
    };
    validateUserToken();
  }, [token, email]);

  if (isAuthorized === null) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <Loading />
        {waking && <p role="status" style={{ color: "#555" }}>{WAKING_MESSAGE}</p>}
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
