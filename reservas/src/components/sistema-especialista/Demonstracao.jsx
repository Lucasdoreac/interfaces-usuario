import React, { useMemo, useState } from "react";
import { localizacao, recomendar, STATUS } from "../../especialista/motor";
import { SALAS_SINTETICAS } from "../../especialista/dadosSinteticos";

const RECURSOS = ["projetor", "computadores"];
const CAMPI = ["Sede", "Rezende"];
const ROTULO_STATUS = {
  [STATUS.ATENDE]: "Atende",
  [STATUS.NAO_ATENDE]: "Não atende",
  [STATUS.INDETERMINADA]: "Falta dado",
};

function LocalizacaoSala({ sala }) {
  const loc = localizacao(sala);
  const partes = Object.entries(loc.conhecidos).map(([campo, f]) => `${campo}: ${f.valor}`);
  return (
    <p className="mb-1">
      <strong>Localização:</strong> {partes.length ? partes.join(" · ") : "nenhum dado confirmado"}
      {loc.ausentes.length > 0 && <> — <em>ausente: {loc.ausentes.join(", ")}</em></>}
    </p>
  );
}

function CartaoSala({ avaliada, sala }) {
  return (
    <li className="mb-3">
      <strong>{avaliada.rotulo}</strong> — {ROTULO_STATUS[avaliada.status]}
      <ul>
        {avaliada.justificativas.map((j) => (
          <li key={j.regra}>
            <code>{j.regra}</code>: {j.motivo}
            {j.fato && <> (fonte: {j.fato.fonte})</>}
          </li>
        ))}
      </ul>
      <LocalizacaoSala sala={sala} />
    </li>
  );
}

function Grupo({ titulo, itens, vazio }) {
  const porId = Object.fromEntries(SALAS_SINTETICAS.map((s) => [s.id, s]));
  return (
    <section aria-label={titulo} className="mt-3">
      <h3 className="h5">{titulo} ({itens.length})</h3>
      {itens.length === 0 ? <p>{vazio}</p> : <ul className="list-unstyled">{itens.map((a) => <CartaoSala key={a.salaId} avaliada={a} sala={porId[a.salaId]} />)}</ul>}
    </section>
  );
}

const Demonstracao = () => {
  const [participantes, setParticipantes] = useState("30");
  const [recursos, setRecursos] = useState(["projetor"]);
  const [campus, setCampus] = useState("Sede");

  const pedido = useMemo(() => ({
    participantes: participantes === "" ? undefined : Number.parseInt(participantes, 10),
    recursos,
    campus: campus || undefined,
  }), [participantes, recursos, campus]);
  const r = useMemo(() => recomendar(SALAS_SINTETICAS, pedido), [pedido]);

  const alternar = (recurso) =>
    setRecursos((atual) => (atual.includes(recurso) ? atual.filter((x) => x !== recurso) : [...atual, recurso]));

  return (
    <section id="demonstracao" aria-labelledby="demonstracao-titulo" className="mt-5">
      <h2 id="demonstracao-titulo">Demonstração</h2>
      <p>
        Funciona com quatro salas <strong>sintéticas</strong>, criadas só para este exemplo: elas não
        representam salas da UDF e nada é gravado. Mude o pedido e veja a recomendação mudar, com a regra e a
        fonte de cada decisão.
      </p>
      <form onSubmit={(e) => e.preventDefault()} className="row g-3 align-items-end">
        <div className="col-sm-4">
          <label htmlFor="demo-participantes" className="form-label">Participantes</label>
          <input id="demo-participantes" className="form-control" type="number" min="1" inputMode="numeric" value={participantes} onChange={(e) => setParticipantes(e.target.value)} />
        </div>
        <div className="col-sm-4">
          <label htmlFor="demo-campus" className="form-label">Campus</label>
          <select id="demo-campus" className="form-select" value={campus} onChange={(e) => setCampus(e.target.value)}>
            <option value="">Qualquer</option>
            {CAMPI.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <fieldset className="col-sm-4">
          <legend className="form-label fs-6">Recursos necessários</legend>
          {RECURSOS.map((rec) => (
            <div className="form-check form-check-inline" key={rec}>
              <input id={`demo-${rec}`} className="form-check-input" type="checkbox" checked={recursos.includes(rec)} onChange={() => alternar(rec)} />
              <label htmlFor={`demo-${rec}`} className="form-check-label">{rec}</label>
            </div>
          ))}
        </fieldset>
      </form>
      <div aria-live="polite">
        {r.semCriterio ? (
          <p className="mt-3">Informe participantes, recursos ou campus. Sem nenhum critério, nada é recomendado.</p>
        ) : (
          <>
            <Grupo titulo="Recomendadas" itens={r.recomendadas} vazio="Nenhuma sala atende a todos os critérios." />
            <Grupo titulo="Faltam dados para decidir" itens={r.indeterminadas} vazio="Nenhuma sala com dado ausente." />
            <Grupo titulo="Não atendem" itens={r.rejeitadas} vazio="Nenhuma sala rejeitada." />
            {r.regrasNaoValidadas.length > 0 && (
              <p className="small">Regras ainda sem validação humana: {r.regrasNaoValidadas.join(", ")}.</p>
            )}
          </>
        )}
      </div>
    </section>
  );
};

export default Demonstracao;
