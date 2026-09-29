import EventTypeSelection from "../../src/pages/event-type-selection/EventTypeSelection";
import PrivateRoute from "../../src/PrivateRoute";

export default function EventTypeSelectionRoute() {
  return <PrivateRoute element={EventTypeSelection} />;
}
