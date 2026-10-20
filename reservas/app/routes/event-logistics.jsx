import EventLogistics from "../../src/pages/event-logistics/EventLogistics";
import EventTypeProtectedRoute from "../../src/EventTypeProtectedRoute";

export default function EventLogisticsRoute() {
  return (
    <EventTypeProtectedRoute
      element={EventLogistics}
      restrictedFor={["class", "exam"]}
      fallbackPath="/event/schedule"
    />
  );
}
