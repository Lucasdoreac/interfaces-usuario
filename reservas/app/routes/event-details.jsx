import EventDetails from "../../src/pages/event-details/EventDetails";
import EventTypeProtectedRoute from "../../src/EventTypeProtectedRoute";

export default function EventDetailsRoute() {
  return (
    <EventTypeProtectedRoute
      element={EventDetails}
      restrictedFor={["class", "exam"]}
      fallbackPath="/event/schedule"
    />
  );
}
