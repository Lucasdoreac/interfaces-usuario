import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import App from "./App";

test("renders home and navigates to organizer with React Router", () => {
  localStorage.clear();

  render(<App />);

  const organizerButton = screen.getByRole("button", { name: "ORGANIZADOR" });
  expect(organizerButton).toBeInTheDocument();

  fireEvent.click(organizerButton);

  expect(
    screen.getByPlaceholderText("Digite seu email@udf.edu.br"),
  ).toBeInTheDocument();
});
