import "./Navbar.scss";
import { useEffect, useState, useSyncExternalStore } from "react";
import { AiOutlineClose, AiOutlineMenu } from "react-icons/ai";
import { Link, useLocation, useNavigate } from 'react-router';
import { endSession, hasSession, subscribeSession } from "../../utils/session";

const Navbar = () => {
    const navigate = useNavigate(); // useNavigate para alterar a URL
    const location = useLocation();
    const [menuOpen, setMenuOpen] = useState(false);
    const loggedIn = useSyncExternalStore(
        subscribeSession,
        () => hasSession(globalThis.localStorage),
        () => false,
    );

    useEffect(() => {
        if (location.state?.loggedOut) endSession(globalThis.localStorage);
    }, [location]);

    const go = (path, state) => {
        setMenuOpen(false);
        navigate(path, state ? { state } : undefined);
    };

    const logout = () => go('/organizer', { loggedOut: true });

    return (
        <nav id="nav" className={menuOpen ? "nav-visible" : undefined}>
            <div className="nav left">
        <span className="gradient skew">
          <h1 className="logo un-skew mt-4">
            <Link to="/" onClick={() => setMenuOpen(false)}>LabTech UDF</Link>
          </h1>
        </span>
                <button
                    id="menu"
                    type="button"
                    className="btn-nav"
                    aria-label={menuOpen ? "Fechar menu" : "Abrir menu"}
                    aria-expanded={menuOpen}
                    aria-controls="nav-links"
                    onClick={() => setMenuOpen((open) => !open)}
                >
                    {menuOpen ? <AiOutlineClose size="24px" /> : <AiOutlineMenu size="24px" />}
                </button>
            </div>
            <div id="nav-links" className="nav right">
        <Link className="nav-link" to="/espacos" onClick={() => setMenuOpen(false)}>
          <span className="nav-link-span">
            <span className="u-nav">Espaços</span>
          </span>
        </Link>
        <Link className="nav-link" to="/organizer" onClick={() => setMenuOpen(false)}>
          <span className="nav-link-span">
            <span className="u-nav">Organizador</span>
          </span>
        </Link>
        {loggedIn && (
          <button type="button" id="logout" className="nav-link" onClick={logout}>
            <span className="nav-link-span"><span className="u-nav">Sair</span></span>
          </button>
        )}
            </div>
        </nav>

    );
  };

export default Navbar;
