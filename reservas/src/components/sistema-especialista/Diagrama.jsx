import React from "react";

const traco = { stroke: "currentColor", strokeWidth: 1.5, fill: "none" };
const FONTE = { fill: "currentColor", fontSize: 13, fontFamily: "inherit" };

// Ponta fechada: chamada/associação dirigida. Ponta aberta: retorno e dependência (UML 2.5.1).
function Marcador({ id }) {
  return (
    <defs>
      <marker id={id} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" fill="currentColor" />
      </marker>
      <marker id={`${id}-aberta`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </marker>
    </defs>
  );
}

function centro(e) {
  if (e.forma === "ator") return { x: e.x, y: e.y + 30 };
  return { x: e.x + e.w / 2, y: e.y + e.h / 2 };
}

// Ponto na borda do retângulo/elipse/losango de `e` na direção de `alvo`.
function borda(e, alvo) {
  const c = centro(e);
  const dx = alvo.x - c.x;
  const dy = alvo.y - c.y;
  if (e.forma === "ator") return { x: c.x + Math.sign(dx) * 14, y: c.y };
  const mw = e.w / 2;
  const mh = e.h / 2;
  let t;
  if (e.forma === "elipse" || e.forma === "inicio" || e.forma === "fim") t = 1 / Math.sqrt((dx / mw) ** 2 + (dy / mh) ** 2 || 1);
  else if (e.forma === "decisao") t = 1 / (Math.abs(dx) / mw + Math.abs(dy) / mh || 1);
  else t = 1 / Math.max(Math.abs(dx) / mw, Math.abs(dy) / mh || 0.0001);
  return { x: c.x + dx * t, y: c.y + dy * t };
}

function Alternativa({ texto }) {
  return <p className="mt-2"><strong>Em texto:</strong> {texto}</p>;
}

function Linhas({ x, y, itens, tamanho = 12 }) {
  return itens.map((t, i) => <text key={`${i}-${t}`} x={x} y={y + i * 17} {...FONTE} fontSize={tamanho}>{t}</text>);
}

function Caixa({ e }) {
  const comEst = Boolean(e.estereotipo);
  const tituloY = e.y + (comEst ? 32 : 20);
  const sepY = tituloY + 8;
  const compartimentos = e.atributos || e.operacoes;
  return (
    <g>
      <rect x={e.x} y={e.y} width={e.w} height={e.h} rx="4" {...traco} />
      {comEst && <text x={e.x + e.w / 2} y={e.y + 15} textAnchor="middle" {...FONTE} fontSize={11}>{`«${e.estereotipo}»`}</text>}
      <text x={e.x + e.w / 2} y={tituloY} textAnchor="middle" {...FONTE} fontWeight="bold">{e.titulo}</text>
      <line x1={e.x} y1={sepY} x2={e.x + e.w} y2={sepY} {...traco} />
      {compartimentos ? (
        <>
          <Linhas x={e.x + 10} y={sepY + 18} itens={e.atributos || []} />
          <line x1={e.x} y1={sepY + 8 + (e.atributos || []).length * 17 + 4} x2={e.x + e.w} y2={sepY + 8 + (e.atributos || []).length * 17 + 4} {...traco} />
          <Linhas x={e.x + 10} y={sepY + 8 + (e.atributos || []).length * 17 + 22} itens={e.operacoes || []} />
        </>
      ) : (
        <Linhas x={e.x + 10} y={sepY + 19} itens={e.linhas || []} />
      )}
    </g>
  );
}

function Elemento({ e }) {
  if (e.forma === "ator") {
    return (
      <g>
        <circle cx={e.x} cy={e.y} r="9" {...traco} />
        <path d={`M${e.x},${e.y + 9} V${e.y + 36} M${e.x - 14},${e.y + 18} H${e.x + 14} M${e.x},${e.y + 36} L${e.x - 12},${e.y + 52} M${e.x},${e.y + 36} L${e.x + 12},${e.y + 52}`} {...traco} />
        <text x={e.x} y={e.y + 70} textAnchor="middle" {...FONTE}>{e.rotulo}</text>
      </g>
    );
  }
  if (e.forma === "elipse") {
    return (
      <g>
        <ellipse cx={e.x + e.w / 2} cy={e.y + e.h / 2} rx={e.w / 2} ry={e.h / 2} {...traco} strokeDasharray={e.tracejado ? "5 4" : undefined} />
        <text x={e.x + e.w / 2} y={e.y + e.h / 2 + 4} textAnchor="middle" {...FONTE}>{e.rotulo}</text>
      </g>
    );
  }
  if (e.forma === "inicio") return <circle cx={e.x + e.w / 2} cy={e.y + e.h / 2} r={e.w / 2} fill="currentColor" stroke="currentColor" />;
  if (e.forma === "fim") {
    return (
      <g>
        <circle cx={e.x + e.w / 2} cy={e.y + e.h / 2} r={e.w / 2} {...traco} />
        <circle cx={e.x + e.w / 2} cy={e.y + e.h / 2} r={e.w / 2 - 4} fill="currentColor" stroke="currentColor" />
      </g>
    );
  }
  if (e.forma === "decisao") {
    const { x, y, w, h } = e;
    const linhas = e.rotulo.split("\n");
    return (
      <g>
        <polygon points={`${x + w / 2},${y} ${x + w},${y + h / 2} ${x + w / 2},${y + h} ${x},${y + h / 2}`} {...traco} />
        {linhas.map((t, i) => <text key={t} x={x + w / 2} y={y + h / 2 + 4 + (i - (linhas.length - 1) / 2) * 14} textAnchor="middle" {...FONTE} fontSize={11}>{t}</text>)}
      </g>
    );
  }
  if (e.forma === "acao") {
    const linhas = e.rotulo.split("\n");
    return (
      <g>
        <rect x={e.x} y={e.y} width={e.w} height={e.h} rx="14" {...traco} />
        {linhas.map((t, i) => <text key={t} x={e.x + e.w / 2} y={e.y + e.h / 2 + 4 + (i - (linhas.length - 1) / 2) * 15} textAnchor="middle" {...FONTE} fontSize={12}>{t}</text>)}
      </g>
    );
  }
  if (e.forma === "regiao") {
    return (
      <g>
        <rect x={e.x} y={e.y} width={e.w} height={e.h} rx="6" {...traco} strokeDasharray="6 4" />
        <text x={e.x + 10} y={e.y + 16} {...FONTE} fontSize={12} fontStyle="italic">{e.rotulo}</text>
      </g>
    );
  }
  return <Caixa e={e} />;
}

export function DiagramaGeral({ d }) {
  const porId = Object.fromEntries(d.elementos.map((e) => [e.id, e]));
  const marc = `seta-${d.id}`;
  const regioes = d.elementos.filter((e) => e.forma === "regiao");
  const demais = d.elementos.filter((e) => e.forma !== "regiao");
  return (
    <figure id={d.id} className="mt-4">
      <figcaption><h3 className="h5">{d.titulo}</h3></figcaption>
      <div style={{ overflowX: "auto" }}>
        <svg role="img" aria-label={`${d.titulo}. ${d.alternativa}`} viewBox={`0 0 ${d.largura} ${d.altura}`} width="100%" style={{ minWidth: 640, maxWidth: d.largura }}>
          <Marcador id={marc} />
          {d.fronteira && (
            <g>
              <rect x={d.fronteira.x} y={d.fronteira.y} width={d.fronteira.w} height={d.fronteira.h} rx="6" {...traco} />
              <text x={d.fronteira.x + 10} y={d.fronteira.y + 18} {...FONTE} fontWeight="bold">{d.fronteira.rotulo}</text>
            </g>
          )}
          {regioes.map((e) => <Elemento key={e.id} e={e} />)}
          {d.ligacoes.map((l) => {
            const a = porId[l.de];
            const b = porId[l.para];
            const p1 = borda(a, centro(b));
            const p2 = borda(b, centro(a));
            const mx = (p1.x + p2.x) / 2;
            const my = (p1.y + p2.y) / 2;
            const perto = (p, q, k) => ({ x: p.x + (q.x - p.x) * k, y: p.y + (q.y - p.y) * k });
            const mult = l.multiplicidadePara && perto(p2, p1, 0.12);
            const multDe = l.multiplicidadeDe && perto(p1, p2, 0.12);
            const seta = d.fronteira || l.semSeta ? undefined : `url(#${marc}${l.tracejada ? "-aberta" : ""})`;
            return (
              <g key={`${l.de}-${l.para}`}>
                <line x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y} {...traco} strokeDasharray={l.tracejada ? "6 4" : undefined} markerEnd={seta} />
                {l.rotulo && <text x={mx} y={my - 5} textAnchor="middle" {...FONTE} fontSize={11} stroke="var(--bs-body-bg, Canvas)" strokeWidth="4" paintOrder="stroke">{l.rotulo}</text>}
                {mult && <text x={mult.x + 6} y={mult.y - 6} {...FONTE} fontSize={11}>{l.multiplicidadePara}</text>}
                {multDe && <text x={multDe.x + 6} y={multDe.y - 6} {...FONTE} fontSize={11}>{l.multiplicidadeDe}</text>}
              </g>
            );
          })}
          {demais.map((e) => <Elemento key={e.id} e={e} />)}
        </svg>
      </div>
      <p className="small">{d.legenda}</p>
      <Alternativa texto={d.alternativa} />
    </figure>
  );
}

export function DiagramaSequencia({ d }) {
  const passo = 190;
  const topo = 64;
  const linha = 40;
  const largura = 40 + passo * d.participantes.length;
  const altura = topo + linha * d.mensagens.length + 24;
  const x = (i) => 20 + passo / 2 + i * passo;
  const marc = `seta-${d.id}`;
  return (
    <figure id={d.id} className="mt-4">
      <figcaption><h3 className="h5">{d.titulo}</h3></figcaption>
      <div style={{ overflowX: "auto" }}>
        <svg role="img" aria-label={`${d.titulo}. ${d.alternativa}`} viewBox={`0 0 ${largura} ${altura}`} width="100%" style={{ minWidth: 640, maxWidth: largura }}>
          <Marcador id={marc} />
          {d.participantes.map((p, i) => (
            <g key={p}>
              <rect x={x(i) - 70} y="8" width="140" height="30" rx="4" {...traco} />
              <text x={x(i)} y="28" textAnchor="middle" {...FONTE}>{p}</text>
              <line x1={x(i)} y1="38" x2={x(i)} y2={altura - 8} {...traco} strokeDasharray="4 4" />
            </g>
          ))}
          {d.mensagens.map((m, k) => {
            const y = topo + k * linha + 14;
            return (
              <g key={`${k}-${m.texto}`}>
                <line x1={x(m.de)} y1={y} x2={x(m.para)} y2={y} {...traco} strokeDasharray={m.tracejada ? "6 4" : undefined} markerEnd={m.tracejada ? `url(#${marc}-aberta)` : `url(#${marc})`} />
                <text x={(x(m.de) + x(m.para)) / 2} y={y - 6} textAnchor="middle" {...FONTE} fontSize={12}>{`${k + 1}. ${m.texto}`}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <p className="small">{d.legenda}</p>
      <Alternativa texto={d.alternativa} />
    </figure>
  );
}
