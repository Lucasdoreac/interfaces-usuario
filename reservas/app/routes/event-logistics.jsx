import EventLogistics from "../../src/pages/event-logistics/EventLogistics";
import EventTypeProtectedRoute from "../../src/EventTypeProtectedRoute";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Logística do evento");
}

export default function EventLogisticsRoute() {
  return (
    <EventTypeProtectedRoute
      element={EventLogistics}
      restrictedFor={["class", "exam"]}
      fallbackPath="/event/schedule"
    />
  );
}
