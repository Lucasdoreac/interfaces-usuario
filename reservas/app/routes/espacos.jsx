import Espacos from "../../src/pages/espacos/Espacos";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Espaços e orientações");
}

export default function EspacosRoute() {
  return <Espacos />;
}
