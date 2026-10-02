import { Link, Outlet, useLocation } from "react-router";
import { FormProvider } from "../../src/context/FormContext";
import { hasInvalidEventIdParam } from "../../src/utils/eventId";

export default function EventLayoutRoute() {
  const { search } = useLocation();
  // A crafted ?eventId= never reaches a page or a request: say so and offer the way out.
  if (hasInvalidEventIdParam(search)) {
    return (
      <main className="container py-5" role="alert">
        <h1>Evento inválido</h1>
        <p>O link que você abriu tem um identificador de evento incorreto.</p>
        <Link to="/event/mine" replace>Ir para Meus eventos</Link>
      </main>
    );
  }
  return (
    <FormProvider>
      <Outlet />
    </FormProvider>
  );
}
