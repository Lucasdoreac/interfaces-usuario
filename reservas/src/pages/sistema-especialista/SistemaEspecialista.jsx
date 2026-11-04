import React from "react";
import { ESTADOS, SECOES } from "../../especialista/documentacao";

const SistemaEspecialista = () => (
  <div className="container py-4">
    <h1>Sistema especialista de salas</h1>
    <p>
      Documentação do que foi pedido, do que já existe e do que falta. Cada item diz de onde vem e em
      que pé está; o que não tem fonte escrita aparece como pendente.
    </p>
    <nav aria-label="Seções da documentação">
      <ul>
        {SECOES.map((s) => (
          <li key={s.id}>
            <a href={`#${s.id}`}>{s.titulo}</a>
          </li>
        ))}
      </ul>
    </nav>
    {SECOES.map((s) => (
      <section key={s.id} id={s.id} aria-labelledby={`${s.id}-titulo`} className="mt-4">
        <h2 id={`${s.id}-titulo`}>{s.titulo}</h2>
        <div className="table-responsive">
          <table className="table align-middle">
            <caption className="visually-hidden">{s.titulo}</caption>
            <thead>
              <tr>
                <th scope="col">Item</th>
                <th scope="col">Fonte</th>
                <th scope="col">Estado</th>
              </tr>
            </thead>
            <tbody>
              {s.itens.map((i) => (
                <tr key={i.texto}>
                  <td>{i.texto}</td>
                  <td>{i.fonte}</td>
                  <td>{ESTADOS[i.estado]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    ))}
  </div>
);

export default SistemaEspecialista;
