import { Outlet } from "react-router";
import { FormProvider } from "../../src/context/FormContext";

export default function EventLayoutRoute() {
  return (
    <FormProvider>
      <Outlet />
    </FormProvider>
  );
}
