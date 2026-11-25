import { index, route } from "@react-router/dev/routes";

export default [
  index("routes/home.jsx"),
  route("organizer", "routes/organizer.jsx"),
  route("auth/callback", "routes/auth-callback.jsx"),
  route("access-denied", "routes/access-denied.jsx"),
  route("event", "routes/event-layout.jsx", [
    route("type-selection", "routes/event-type-selection.jsx"),
    route("basic-info", "routes/event-basic-info.jsx"),
    route("details", "routes/event-details.jsx"),
    route("logistics", "routes/event-logistics.jsx"),
    route("schedule", "routes/event-schedule.jsx"),
    route("confirm-data", "routes/event-confirm-data.jsx"),
    route("confirmation", "routes/event-confirmation.jsx"),
    route("mine", "routes/my-events.jsx"),
  ]),
];
