import AuthCallBack from "../../src/pages/auth-callback/AuthCallBack";
import { pageMeta } from "../../src/routeMeta";

export function meta() {
  return pageMeta("Entrar");
}

export default function AuthCallbackRoute() {
  return <AuthCallBack />;
}
