import "./index.scss";
function Loading({ label = "Carregando" }) {
  return (
    <>
      <div className="lds-roller" aria-hidden="true">
        <div></div>
        <div></div>
        <div></div>
        <div></div>
        <div></div>
        <div></div>
        <div></div>
        <div></div>
      </div>
      <span className="visually-hidden">{label}</span>
    </>
  );
}

export default Loading;
