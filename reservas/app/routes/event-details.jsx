import EventDetails from "../../src/pages/event-details/EventDetails";
import EventTypeProtectedRoute from "../../src/EventTypeProtectedRoute";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Detalhes do evento");
}

export default function EventDetailsRoute() {
  return (
    <EventTypeProtectedRoute
      element={EventDetails}
      restrictedFor={["class", "exam"]}
      fallbackPath="/event/schedule"
    />
  );
}
