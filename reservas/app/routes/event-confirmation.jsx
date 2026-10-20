import EventConfirmation from "../../src/pages/event-confirmation/EventConfirmation";
import PrivateRoute from "../../src/PrivateRoute";

export default function EventConfirmationRoute() {
  return <PrivateRoute element={EventConfirmation} />;
}
