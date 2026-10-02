import "./StepIndicator.scss";
import { useLocation } from "react-router";
import { EVENT_STEPS, stepOf } from "../../utils/eventSteps";

// "Etapa 3 de 6" with one dot per step, for the event request wizard.
const StepIndicator = () => {
  const step = stepOf(useLocation().pathname);
  if (!step) return null;
  return (
    <div
      className="step-indicator"
      role="progressbar"
      aria-valuemin={1}
      aria-valuemax={step.total}
      aria-valuenow={step.current}
      aria-label={`Etapa ${step.current} de ${step.total}: ${step.label}`}
    >
      <ol className="step-dots">
        {EVENT_STEPS.map(({ path }, index) => (
          <li
            key={path}
            className={index + 1 < step.current ? "done" : index + 1 === step.current ? "current" : undefined}
          />
        ))}
      </ol>
      <p className="step-text">
        Etapa {step.current} de {step.total} · {step.label}
      </p>
    </div>
  );
};

export default StepIndicator;
