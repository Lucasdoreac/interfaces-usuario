import React from "react";
import "./App.scss";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home/Home";
import Organizer from "./pages/organizer/Organizer";
import Navbar from "./components/Navbar/Navbar";
import AuthCallBack from "./pages/auth-callback/AuthCallBack";
import EventBasicInfo from "./pages/event-basic-info/EventBasicInfo";
import EventDetails from "./pages/event-details/EventDetails";
import EventLogistics from "./pages/event-logistics/EventLogistics";
import AccessDenied from "./pages/access-denied/AccessDenied";
import PrivateRoute from "./PrivateRoute";
import EventTypeProtectedRoute from "./EventTypeProtectedRoute"; // Novo componente
import { FormProvider } from "./context/FormContext";
import EventConfirmation from "./pages/event-confirmation/EventConfirmation";
import MyEvents from "./pages/meus-eventos/MyEvents";
import EventSchedule from "./pages/event-schedule/EventSchedule";
import EventConfirmData from "./pages/event-confirm-data/EventConfirmData";
import EventTypeSelection from "./pages/event-type-selection/EventTypeSelection";

function App() {
  return (
    <BrowserRouter>
      <div className="App">
        <Navbar />
        <section id="paginaInicial" className="section-padding">
          <div>
            <div className="row justify-content-center">
              <div className="col-md-12 col-sm-12 col-12">
                <div className="card">
                  <Routes>
                    {/* Home */}
                    <Route path="/" element={<Home />} />

                    {/* Organizer / Coordination Flow */}
                    <Route path="/organizer" element={<Organizer />} />
                    <Route path="/auth/callback" element={<AuthCallBack />} />

                    {/* Event Routes with FormProvider */}
                    <Route
                      path="/event/*"
                      element={
                        <FormProvider>
                          <EventRoutes />
                        </FormProvider>
                      }
                    />
                    <Route path="/access-denied" element={<AccessDenied />} />
                  </Routes>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </BrowserRouter>
  );
}

function EventRoutes() {
  return (
    <Routes>
      {/* Event Creation Flow */}
      <Route
        path="/type-selection"
        element={<PrivateRoute element={EventTypeSelection} />}
      />

      {/* Rotas protegidas com base no tipo de evento */}
      <Route
        path="/basic-info"
        element={
          <EventTypeProtectedRoute
            element={EventBasicInfo}
            restrictedFor={["class", "exam"]}
            fallbackPath="/event/schedule"
          />
        }
      />
      <Route
        path="/details"
        element={
          <EventTypeProtectedRoute
            element={EventDetails}
            restrictedFor={["class", "exam"]}
            fallbackPath="/event/schedule"
          />
        }
      />
      <Route
        path="/logistics"
        element={
          <EventTypeProtectedRoute
            element={EventLogistics}
            restrictedFor={["class", "exam"]}
            fallbackPath="/event/schedule"
          />
        }
      />

      {/* Rotas que são acessíveis para todos os tipos de evento */}
      <Route
        path="/schedule"
        element={<PrivateRoute element={EventSchedule} />}
      />
      <Route
        path="/confirm-data"
        element={<PrivateRoute element={EventConfirmData} />}
      />
      <Route
        path="/confirmation"
        element={<PrivateRoute element={EventConfirmation} />}
      />
      <Route path="/mine" element={<PrivateRoute element={MyEvents} />} />
    </Routes>
  );
}

export default App;
