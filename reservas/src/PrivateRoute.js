import React from "react";
import { Navigate } from "react-router-dom";

const LOCAL_STORAGE_KEYS = {
  TOKEN: "token",
};

const PrivateRoute = ({ element: Component, ...rest }) => {
  const token = localStorage.getItem(LOCAL_STORAGE_KEYS.TOKEN);

  return token ? <Component {...rest} /> : <Navigate to="/acesso-negado" />;
};

export default PrivateRoute;
