import EventSchedule from "../../src/pages/event-schedule/EventSchedule";
import PrivateRoute from "../../src/PrivateRoute";

export default function EventScheduleRoute() {
  return <PrivateRoute element={EventSchedule} />;
}
