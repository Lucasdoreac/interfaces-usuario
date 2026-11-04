import React from "react";
import { ESTADOS, SECOES } from "../../especialista/documentacao";
import { CASOS_DE_USO, CLASSES, COMPONENTES, SEQUENCIA, TECNOLOGIAS } from "../../especialista/diagramas";
import { REGRAS } from "../../especialista/motor";
import { DiagramaGeral, DiagramaSequencia } from "../../components/sistema-especialista/Diagrama";
import Demonstracao from "../../components/sistema-especialista/Demonstracao";

const INDICE = [
  ["pitch", "Pitch"],
  ["demonstracao", "Demonstração"],
  ["como-funciona", "Como o especialista decide"],
  ["uml", "UML"],
  ["tecnologia", "Fundamentos de tecnologia"],
  ...SECOES.map((s) => [s.id, s.titulo]),
];

const SistemaEspecialista = () => (
  <div className="container py-4 sistema-especialista">
    <h1>Sistema especialista de salas</h1>
    <nav aria-label="Seções da documentação">
      <ul>
        {INDICE.map(([id, titulo]) => (
          <li key={id}><a href={`#${id}`}>{titulo}</a></li>
        ))}
      </ul>
    </nav>

    <section id="pitch" aria-labelledby="pitch-titulo" className="mt-4">
      <h2 id="pitch-titulo">Pitch</h2>
      <p><strong>Problema.</strong> Quem precisa de uma sala escolhe sem saber se ela comporta o evento, tem os recursos e onde fica. A confirmação é manual e a informação de localização é pouca.</p>
      <p><strong>Solução.</strong> Um sistema especialista que recomenda salas e explica: para cada sala mostra qual regra foi aplicada, qual fato foi usado e de onde ele vem. Quando falta dado, diz que falta, em vez de chutar. A localização aparece separada da recomendação e só com o que está confirmado.</p>
      <p><strong>Diferencial.</strong> Explicável, com validação humana das regras e sem inventar dados. A decisão final da reserva continua com a Assessoria Acadêmica.</p>
    </section>

    <Demonstracao />

    <section id="como-funciona" aria-labelledby="como-titulo" className="mt-5">
      <h2 id="como-titulo">Como o especialista decide</h2>
      <p>
        <strong>Base de conhecimento:</strong> fatos sobre cada sala (campus, prédio, andar, capacidade, recursos), cada um com valor e fonte,
        e regras do tipo SE–ENTÃO. <strong>Motor de inferência:</strong> aplica as regras aos fatos e conclui “atende”, “não atende” ou
        “falta dado”, devolvendo a justificativa. Fato ausente nunca vira “atende”, e sem nenhum critério nada é recomendado.
        Regras sem validação humana são sinalizadas no resultado.
      </p>
      <div className="table-responsive">
        <table className="table align-middle">
          <caption className="visually-hidden">Regras da base de conhecimento</caption>
          <thead>
            <tr><th scope="col">Regra</th><th scope="col">SE–ENTÃO</th><th scope="col">Validação humana</th></tr>
          </thead>
          <tbody>
            {REGRAS.map((r) => (
              <tr key={r.id}>
                <td><code>{r.id}</code></td>
                <td>{r.descricao}</td>
                <td>{r.validadaPor ? `Validada por ${r.validadaPor}` : "Pendente"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>

    <section id="uml" aria-labelledby="uml-titulo" className="mt-5">
      <h2 id="uml-titulo">Documentação de software: UML</h2>
      <p>Diagramas resumem o código e identificam o que ainda não foi implementado. São esquemas simplificados: a notação UML formal e a revisão acadêmica permanecem pendentes. Cada um tem uma versão em texto.</p>
      <DiagramaGeral d={CASOS_DE_USO} />
      <DiagramaGeral d={COMPONENTES} />
      <DiagramaGeral d={CLASSES} />
      <DiagramaSequencia d={SEQUENCIA} />
    </section>

    <section id="tecnologia" aria-labelledby="tec-titulo" className="mt-5">
      <h2 id="tec-titulo">Fundamentos de tecnologia</h2>
      <div className="table-responsive">
        <table className="table align-middle">
          <caption className="visually-hidden">Tecnologias por camada</caption>
          <thead>
            <tr><th scope="col">Camada</th><th scope="col">Tecnologias</th><th scope="col">Onde conferir</th></tr>
          </thead>
          <tbody>
            {TECNOLOGIAS.map((t) => (
              <tr key={t.camada}><th scope="row">{t.camada}</th><td>{t.itens}</td><td>{t.onde}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>

    {SECOES.map((s) => (
      <section key={s.id} id={s.id} aria-labelledby={`${s.id}-titulo`} className="mt-5">
        <h2 id={`${s.id}-titulo`}>{s.titulo}</h2>
        <div className="table-responsive">
          <table className="table align-middle">
            <caption className="visually-hidden">{s.titulo}</caption>
            <thead>
              <tr><th scope="col">Item</th><th scope="col">Fonte</th><th scope="col">Estado</th></tr>
            </thead>
            <tbody>
              {s.itens.map((i) => (
                <tr key={i.texto}><td>{i.texto}</td><td>{i.fonte}</td><td>{ESTADOS[i.estado]}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    ))}
  </div>
);

export default SistemaEspecialista;
