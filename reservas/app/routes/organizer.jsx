import Organizer from "../../src/pages/organizer/Organizer";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Organizador");
}

export default function OrganizerRoute() {
  return <Organizer />;
}
