import React from "react";
import { ESTADOS, SECOES } from "../../especialista/documentacao";
import { ATIVIDADES, CASOS_DE_USO, CLASSES, COMPONENTES, SEQUENCIA, TECNOLOGIAS, NOTA_TECNOLOGIAS } from "../../especialista/diagramas";
import { REGRAS_TRIAGEM } from "../../especialista/triagem";
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
      <p><strong>Problema.</strong> Hipótese a validar com a Coordenação: o pedido de reserva chega à Assessoria e é conferido à mão contra o procedimento (três turnos, limites por dia e por solicitante). Ainda não há pesquisa que meça esse esforço.</p>
      <p><strong>Solução.</strong> Um protótipo de sistema especialista que tria um pedido de reserva contra o procedimento da Assessoria Acadêmica e explica: para cada regra mostra o fato usado, de onde ele vem e como foi derivado. Quando falta dado, diz que falta, em vez de chutar. A consulta de uma sala real por ID mostra só o que o catálogo tem (rótulo e campus) e lista o que falta.</p>
      <p><strong>Diferencial.</strong> Explicável, com encadeamento de fatos e sem inventar dados. A validação humana das regras está prevista, ainda não feita. A decisão final da reserva continua com a Assessoria Acadêmica.</p>
    </section>

    <Demonstracao />

    <section id="como-funciona" aria-labelledby="como-titulo" className="mt-5">
      <h2 id="como-titulo">Como o especialista decide</h2>
      <p>
        <strong>Base de conhecimento:</strong> fatos do pedido (participantes, datas e turnos, exceção) e regras do tipo SE–ENTÃO do
        procedimento. <strong>Motor de inferência:</strong> encadeia para a frente: dos fatos informados deriva outros (por exemplo, as
        reservas de cada dia levam a “dia dentro do limite”) até não haver o que derivar, e conclui “atende”, “não atende” ou “falta dado”,
        devolvendo a justificativa. Fato que não pôde ser derivado nunca vira “atende”. Regras sem validação humana são sinalizadas no resultado.
      </p>
      <div className="table-responsive">
        <table className="table align-middle">
          <caption className="visually-hidden">Regras da base de conhecimento</caption>
          <thead>
            <tr><th scope="col">Regra</th><th scope="col">SE–ENTÃO</th><th scope="col">Validação humana</th></tr>
          </thead>
          <tbody>
            {REGRAS_TRIAGEM.map((r) => (
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
      <p>Diagramas resumem o código e identificam o que ainda não foi implementado. São esquemas inspirados na UML 2.5.1, não uma prova de conformidade: casos de uso e classes são modelos conceituais; componentes, atividades e sequência seguem o código e a configuração, com a evidência de cada ligação indicada. A revisão acadêmica permanece pendente. Cada diagrama tem uma versão em texto.</p>
      <DiagramaGeral d={CASOS_DE_USO} />
      <DiagramaGeral d={COMPONENTES} />
      <DiagramaGeral d={CLASSES} />
      <DiagramaGeral d={ATIVIDADES} />
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
      <p className="small">{NOTA_TECNOLOGIAS}</p>
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
