import React from "react";
import "./App.scss";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home/Home";
import Organizer from "./pages/organizer/Organizer";
import EmailCoordination from "./pages/approve-event";
import Navbar from "./components/Navbar/Navbar";
import AuthCallBack from "./pages/auth-callback/AuthCallBack";
import EventBasicInfo from "./pages/event-basic-info/EventBasicInfo";
import EventDetails from "./pages/event-details/EventDetails";
import EventLogistics from "./pages/event-logistics/EventLogistics";
import AccessDenied from "./pages/access-denied/AccessDenied";
import PrivateRoute from "./PrivateRoute";
import { FormProvider } from "./context/FormContext";
import EventConfirmation from "./pages/event-confirmation/EventConfirmation";
import MyEvents from "./pages/meus-eventos/MyEvents";
import EventSchedule from "./pages/event-schedule/EventSchedule";
import EventConfirmData from "./pages/event-confirm-data/EventConfirmData";

function App() {
  return (
    <FormProvider>
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
                      <Route
                        path="/coordination"
                        element={<EmailCoordination />}
                      />

                      {/* Event Creation Flow */}
                      <Route
                        path="/event/basic-info"
                        element={<PrivateRoute element={EventBasicInfo} />}
                      />
                      <Route
                        path="/event/details"
                        element={<PrivateRoute element={EventDetails} />}
                      />
                      <Route
                        path="/event/logistics"
                        element={<PrivateRoute element={EventLogistics} />}
                      />
                      <Route
                        path="/event/schedule"
                        element={<PrivateRoute element={EventSchedule} />}
                      />
                      <Route
                        path="/event/confirm-data"
                        element={<PrivateRoute element={EventConfirmData} />}
                      />
                      <Route
                        path="/event/confirmation"
                        element={<PrivateRoute element={EventConfirmation} />}
                      />

                      {/* Others */}
                      <Route
                        path="/my-events"
                        element={<PrivateRoute element={MyEvents} />}
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
    </FormProvider>
  );
}

export default App;
