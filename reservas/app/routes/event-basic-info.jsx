import EventBasicInfo from "../../src/pages/event-basic-info/EventBasicInfo";
import EventTypeProtectedRoute from "../../src/EventTypeProtectedRoute";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Informações do evento");
}

export default function EventBasicInfoRoute() {
  return (
    <EventTypeProtectedRoute
      element={EventBasicInfo}
      restrictedFor={["class", "exam"]}
      fallbackPath="/event/schedule"
    />
  );
}
