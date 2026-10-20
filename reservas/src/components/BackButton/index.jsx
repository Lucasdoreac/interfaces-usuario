import { AiOutlineLeft } from "react-icons/ai";

// "Voltar" as a real button: focusable, announced as "Voltar", works with Enter and Space.
export default function BackButton({ onClick, label = "Voltar" }) {
  return (
    <button type="button" className="back-button" onClick={onClick}>
      <AiOutlineLeft size="20px" color="white" aria-hidden="true" />
      <span>{label}</span>
    </button>
  );
}
