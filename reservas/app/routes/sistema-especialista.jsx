import SistemaEspecialista from "../../src/pages/sistema-especialista/SistemaEspecialista";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Sistema especialista");
}

export default function SistemaEspecialistaRoute() {
  return <SistemaEspecialista />;
}
