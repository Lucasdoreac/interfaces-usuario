import "./Navbar.scss";
import { useNavigate } from 'react-router-dom';

const Navbar = () => {
    const navigate = useNavigate(); // useNavigate para alterar a URL

    return (
        <nav id="nav">
            <div className="nav left">
        <span className="gradient skew">
          <h1 className="logo un-skew mt-4">
            <span onClick={() => navigate('/')}>LabTech UDF</span>
          </h1>
        </span>
                <button id="menu" className="btn-nav">
                    <span className="fas fa-bars"></span>
                </button>
            </div>
            <div className="nav right">
        <span className="nav-link active" onClick={() => navigate('/organizador')}>
          <span className="nav-link-span">
            <span className="u-nav">Organizador</span>
          </span>
        </span>
            </div>
        </nav>
    );
}

export default Navbar;
