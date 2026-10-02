import EventConfirmation from "../../src/pages/event-confirmation/EventConfirmation";
import PrivateRoute from "../../src/PrivateRoute";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Evento enviado");
}

export default function EventConfirmationRoute() {
  return <PrivateRoute element={EventConfirmation} />;
}
