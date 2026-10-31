import EventTypeSelection from "../../src/pages/event-type-selection/EventTypeSelection";
import PrivateRoute from "../../src/PrivateRoute";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Tipo de evento");
}

export default function EventTypeSelectionRoute() {
  return <PrivateRoute element={EventTypeSelection} />;
}
