import AccessDenied from "../../src/pages/access-denied/AccessDenied";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Acesso negado");
}

export default function AccessDeniedRoute() {
  return <AccessDenied />;
}
