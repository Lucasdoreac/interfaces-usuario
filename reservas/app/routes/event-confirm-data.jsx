import EventConfirmData from "../../src/pages/event-confirm-data/EventConfirmData";
import PrivateRoute from "../../src/PrivateRoute";

export default function EventConfirmDataRoute() {
  return <PrivateRoute element={EventConfirmData} />;
}
