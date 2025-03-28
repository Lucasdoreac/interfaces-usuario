import React, { useState, useEffect } from "react";
import { Navigate } from "react-router-dom";
import apiService from "../src/services/client";
import Loading from "./components/Loading";

const LOCAL_STORAGE_KEYS = {
  TOKEN: "token",
  EMAIL: "userEmail",
};

const PrivateRoute = ({ element: Component, ...rest }) => {
  const [isAuthorized, setIsAuthorized] = useState(null);
  const token = localStorage.getItem(LOCAL_STORAGE_KEYS.TOKEN);
  const email = localStorage.getItem(LOCAL_STORAGE_KEYS.EMAIL);

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
