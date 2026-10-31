import MyEvents from "../../src/pages/meus-eventos/MyEvents";
import PrivateRoute from "../../src/PrivateRoute";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Meus eventos");
}

export default function MyEventsRoute() {
  return <PrivateRoute element={MyEvents} />;
}
