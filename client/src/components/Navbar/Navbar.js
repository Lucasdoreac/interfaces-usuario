import "./Navbar.scss";

const Navbar = () => {
  return (
    <nav id="nav">
      <div className="nav left">
        <span className="gradient skew">
          <h1 className="logo un-skew mt-4">
            <a href="/">LabTech UDF</a>
          </h1></span>
        <button id="menu" className="btn-nav"><span className="fas fa-bars"></span></button>
      </div>
      <div className="nav right">
        <a href="/organizador" className="nav-link active">
          <span className="nav-link-span">
            <span className="u-nav">
              organizador
            </span>
          </span>
        </a>

      </div>
    </nav>


  )



}

export default Navbar;