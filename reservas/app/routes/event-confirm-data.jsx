import EventConfirmData from "../../src/pages/event-confirm-data/EventConfirmData";
import PrivateRoute from "../../src/PrivateRoute";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Confirmar dados");
}

export default function EventConfirmDataRoute() {
  return <PrivateRoute element={EventConfirmData} />;
}
