import EventSchedule from "../../src/pages/event-schedule/EventSchedule";
import PrivateRoute from "../../src/PrivateRoute";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Dia e horário");
}

export default function EventScheduleRoute() {
  return <PrivateRoute element={EventSchedule} />;
}
