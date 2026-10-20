import EventBasicInfo from "../../src/pages/event-basic-info/EventBasicInfo";
import EventTypeProtectedRoute from "../../src/EventTypeProtectedRoute";

export default function EventBasicInfoRoute() {
  return (
    <EventTypeProtectedRoute
      element={EventBasicInfo}
      restrictedFor={["class", "exam"]}
      fallbackPath="/event/schedule"
    />
  );
}
