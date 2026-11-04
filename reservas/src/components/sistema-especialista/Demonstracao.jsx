import React, { useMemo, useState } from "react";
import { localizacao, STATUS } from "../../especialista/motor";
import { TURNOS, triar } from "../../especialista/triagem";
import { carregarSala } from "../../especialista/catalogo";
import apiService from "../../services/client";

const ROTULO_STATUS = {
  [STATUS.ATENDE]: "Atende",
  [STATUS.NAO_ATENDE]: "Não atende",
  [STATUS.INDETERMINADA]: "Falta dado ou decisão",
};
const CONCLUSAO = {
  dentro: "Dentro das regras do procedimento (ainda sem validação da Assessoria).",
  viola: "Viola uma regra do procedimento.",
  assessoria: "Caso excepcional: encaminhar à Assessoria, que decide.",
  incompleto: "Pedido incompleto: faltam dados para decidir.",
};

let proximo = 1;
const novaLinha = () => ({ chave: proximo++, data: "", turno: TURNOS[0] });
const valorFato = (v) => (typeof v === "object" && v !== null ? JSON.stringify(v) : String(v));

function Triagem() {
  const [participantes, setParticipantes] = useState("");
  const [excecao, setExcecao] = useState(false);
  const [linhas, setLinhas] = useState(() => [novaLinha()]);
  const atualizar = (chave, campo, valor) => setLinhas((ls) => ls.map((l) => (l.chave === chave ? { ...l, [campo]: valor } : l)));

  const pedido = useMemo(() => ({
    participantes: participantes === "" ? undefined : Number.parseInt(participantes, 10),
    linhas: linhas.filter((l) => l.data !== "").map(({ data, turno }) => ({ data, turno })),
    excecao,
  }), [participantes, linhas, excecao]);
  const r = useMemo(() => triar(pedido), [pedido]);

  return (
    <div>
      <form onSubmit={(e) => e.preventDefault()} className="row g-3 align-items-end">
        <div className="col-sm-4">
          <label htmlFor="demo-participantes" className="form-label">Participantes</label>
          <input id="demo-participantes" className="form-control" type="number" min="1" inputMode="numeric" value={participantes} onChange={(e) => setParticipantes(e.target.value)} />
        </div>
        <div className="col-sm-8">
          <div className="form-check">
            <input id="demo-excecao" className="form-check-input" type="checkbox" checked={excecao} onChange={(e) => setExcecao(e.target.checked)} />
            <label htmlFor="demo-excecao" className="form-check-label">Caso excepcional (a Assessoria decide)</label>
          </div>
        </div>
        <fieldset className="col-12">
          <legend className="form-label fs-6">Datas e turnos pedidos</legend>
          {linhas.map((l, i) => (
            <div className="row g-2 mb-2" key={l.chave}>
              <div className="col-sm-4">
                <label htmlFor={`demo-data-${l.chave}`} className="visually-hidden">Data do pedido {i + 1}</label>
                <input id={`demo-data-${l.chave}`} className="form-control" type="date" value={l.data} onChange={(e) => atualizar(l.chave, "data", e.target.value)} />
              </div>
              <div className="col-sm-4">
                <label htmlFor={`demo-turno-${l.chave}`} className="visually-hidden">Turno do pedido {i + 1}</label>
                <select id={`demo-turno-${l.chave}`} className="form-select" value={l.turno} onChange={(e) => atualizar(l.chave, "turno", e.target.value)}>
                  {TURNOS.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="col-sm-4">
                <button type="button" className="btn btn-outline-secondary" disabled={linhas.length === 1} onClick={() => setLinhas((ls) => ls.filter((x) => x.chave !== l.chave))}>Remover período {i + 1}</button>
              </div>
            </div>
          ))}
          <button type="button" className="btn btn-secondary" onClick={() => setLinhas((ls) => [...ls, novaLinha()])}>Adicionar período</button>
        </fieldset>
      </form>
      <div aria-live="polite" className="mt-3">
        <p><strong>{CONCLUSAO[r.conclusao]}</strong></p>
        <ul className="list-unstyled">
          {r.justificativas.map((j) => (
            <li key={j.regra} className="mb-2">
              <code>{j.regra}</code> — {ROTULO_STATUS[j.status]}: {j.motivo}
              <div className="small">Regra: {j.descricao} Fonte: {j.fonteRegra}{j.regraValidada ? "" : " (sem validação da Assessoria)"}</div>
              {j.fatos.length > 0 && <div className="small">Fatos usados: {j.fatos.map((f) => `${f.id} = ${valorFato(f.valor)} (${f.fonte})`).join("; ")}</div>}
            </li>
          ))}
        </ul>
        <details>
          <summary>Encadeamento dos fatos ({r.cadeia.length} passos)</summary>
          <ol>
            {r.cadeia.map((c) => <li key={c.produz}><code>{c.produz}</code> = {valorFato(c.valor)}, a partir de {c.deDe.join(", ")} (<code>{c.regra}</code>)</li>)}
          </ol>
        </details>
        {r.avisos.map((a) => <p key={a} className="small mt-2">{a}</p>)}
      </div>
    </div>
  );
}

function ConsultaSala() {
  const [idSala, setIdSala] = useState("");
  const [sala, setSala] = useState(null);
  const [estado, setEstado] = useState("ocioso");
  const consultar = async () => {
    setEstado("carregando");
    try {
      const [s] = await carregarSala(apiService, idSala);
      setSala(s);
      setEstado("ok");
    } catch {
      setSala(null);
      setEstado("erro");
    }
  };
  const loc = sala ? localizacao(sala) : null;
  return (
    <div className="mt-4">
      <h3 className="h5">Consultar uma sala real por ID</h3>
      <p>O catálogo real só traz o rótulo e o campus de cada sala. A consulta mostra o que consta e lista o que falta; não monta trajeto.</p>
      <label htmlFor="demo-id-sala" className="form-label">ID da sala no catálogo</label>
      <input id="demo-id-sala" className="form-control" value={idSala} onChange={(e) => setIdSala(e.target.value)} />
      <button type="button" className="btn btn-primary mt-2" disabled={estado === "carregando"} onClick={consultar}>Consultar catálogo</button>
      <div aria-live="polite">
        {estado === "erro" && <p role="alert">Não foi possível consultar a sala. Confira o ID, a autenticação e a disponibilidade da API.</p>}
        {loc && (
          <p className="mt-2">
            <strong>{loc.rotulo}</strong> — {Object.entries(loc.conhecidos).map(([c, f]) => `${c}: ${f.valor}`).join(" · ") || "nenhum dado de localização"}
            {loc.ausentes.length > 0 && <> — <em>ausente: {loc.ausentes.join(", ")}</em></>}
          </p>
        )}
      </div>
    </div>
  );
}

const Demonstracao = () => (
  <section id="demonstracao" aria-labelledby="demonstracao-titulo" className="mt-5">
    <h2 id="demonstracao-titulo">Demonstração</h2>
    <p>
      Digite um pedido de reserva (participantes, datas e turnos) e veja a triagem contra o procedimento da Assessoria
      Acadêmica, com a regra, os fatos e a fonte de cada decisão. Nada é gravado e nenhuma reserva é feita.
    </p>
    <Triagem />
    <ConsultaSala />
  </section>
);

export default Demonstracao;
