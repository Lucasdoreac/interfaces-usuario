import { Outlet } from "react-router";
import { FormProvider } from "../../src/context/FormContext";
import StepIndicator from "../../src/components/StepIndicator/StepIndicator";

export default function EventLayoutRoute() {
  return (
    <FormProvider>
      <StepIndicator />
      <Outlet />
    </FormProvider>
  );
}
