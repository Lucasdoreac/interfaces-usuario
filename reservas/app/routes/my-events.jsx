import MyEvents from "../../src/pages/meus-eventos/MyEvents";
import PrivateRoute from "../../src/PrivateRoute";

export default function MyEventsRoute() {
  return <PrivateRoute element={MyEvents} />;
}
