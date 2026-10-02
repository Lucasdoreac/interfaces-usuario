// "<Tela> | Reservas UDF" for each route. A leaf route's `meta` replaces the root's,
// so the description travels with the title.
export function pageMeta(screen) {
  return [
    { title: `${screen} | Reservas UDF` },
    {
      name: "description",
      content: "Sistema de reserva de espaços do Centro Universitário UDF.",
    },
  ];
}
