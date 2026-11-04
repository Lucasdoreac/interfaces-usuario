import React, { useMemo, useState } from "react";
import { localizacao, recomendar, STATUS } from "../../especialista/motor";
import { SALAS_SINTETICAS } from "../../especialista/dadosSinteticos";
import { carregarSala } from "../../especialista/catalogo";
import apiService from "../../services/client";

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

function Grupo({ titulo, itens, vazio, salas }) {
  const porId = Object.fromEntries(salas.map((s) => [s.id, s]));
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
  const [salas, setSalas] = useState(SALAS_SINTETICAS);
  const [idSala, setIdSala] = useState("");
  const [estado, setEstado] = useState("sintético");
  const [erro, setErro] = useState("");
  const carregar = async () => {
    setErro("");
    setEstado("carregando");
    try {
      setSalas(await carregarSala(apiService, idSala));
      setCampus("");
      setEstado("catálogo real");
    } catch {
      setSalas(SALAS_SINTETICAS);
      setCampus("Sede");
      setEstado("sintético");
      setErro("Não foi possível consultar a sala. Confira o ID, a autenticação e a disponibilidade da API.");
    }
  };

  const pedido = useMemo(() => ({
    participantes: participantes === "" ? undefined : Number.parseInt(participantes, 10),
    recursos,
    campus: campus || undefined,
  }), [participantes, recursos, campus]);
  const r = useMemo(() => recomendar(salas, pedido), [salas, pedido]);

  const alternar = (recurso) =>
    setRecursos((atual) => (atual.includes(recurso) ? atual.filter((x) => x !== recurso) : [...atual, recurso]));

  return (
    <section id="demonstracao" aria-labelledby="demonstracao-titulo" className="mt-5">
      <h2 id="demonstracao-titulo">Demonstração</h2>
      <p>
        Por padrão usa quatro salas <strong>sintéticas</strong>, criadas só para este exemplo: elas não
        representam salas da UDF e nada é gravado. Mude o pedido e veja a recomendação mudar, com a regra e a
        fonte de cada decisão.
      </p>
      <p>Modo atual: <strong>{estado}</strong>. No catálogo real, o campus é exibido como identificador; capacidade e recursos permanecem ausentes.</p>
      <div className="mb-3">
        <label htmlFor="demo-id-sala" className="form-label">ID da sala no catálogo</label>
        <input id="demo-id-sala" className="form-control" value={idSala} onChange={(e) => setIdSala(e.target.value)} />
        <button type="button" className="btn btn-primary mt-2 me-2" disabled={estado === "carregando"} onClick={carregar}>Consultar catálogo real</button>
        <button type="button" className="btn btn-secondary mt-2" disabled={estado === "carregando"} onClick={() => { setSalas(SALAS_SINTETICAS); setEstado("sintético"); setErro(""); setCampus("Sede"); }}>Usar dados sintéticos</button>
        {erro && <p role="alert">{erro}</p>}
      </div>
      <form onSubmit={(e) => e.preventDefault()} className="row g-3 align-items-end">
        <div className="col-sm-4">
          <label htmlFor="demo-participantes" className="form-label">Participantes</label>
          <input id="demo-participantes" className="form-control" type="number" min="1" inputMode="numeric" value={participantes} onChange={(e) => setParticipantes(e.target.value)} />
        </div>
        <div className="col-sm-4">
          <label htmlFor="demo-campus" className="form-label">Campus</label>
          <select id="demo-campus" className="form-select" value={campus} onChange={(e) => setCampus(e.target.value)}>
            <option value="">Qualquer</option>
            {(estado === "catálogo real" ? (salas[0]?.fatos?.campus ? [salas[0].fatos.campus.valor] : []) : CAMPI).map((c) => <option key={c} value={c}>{c}</option>)}
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
            <Grupo salas={salas} titulo="Recomendadas" itens={r.recomendadas} vazio="Nenhuma sala atende a todos os critérios." />
            <Grupo salas={salas} titulo="Faltam dados para decidir" itens={r.indeterminadas} vazio="Nenhuma sala com dado ausente." />
            <Grupo salas={salas} titulo="Não atendem" itens={r.rejeitadas} vazio="Nenhuma sala rejeitada." />
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
