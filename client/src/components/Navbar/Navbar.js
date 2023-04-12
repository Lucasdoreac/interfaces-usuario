import { Link } from "react-router-dom";
import "./Navbar.scss";

const Navbar = () => {
       return (
        // eslint-disable-next-line jsx-a11y/anchor-is-valid
        <nav id="nav">
      <div className="nav left">
        <span className="gradient skew"><h1 className="logo un-skew"><a href="/">LabTech</a></h1></span>
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