import Home from "../../src/pages/Home/Home";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Início");
}

export default function HomeRoute() {
  return <Home />;
}
