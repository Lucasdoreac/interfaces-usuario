import "./Navbar.scss";
import { useEffect, useState, useSyncExternalStore } from "react";
import { AiOutlineClose, AiOutlineMenu } from "react-icons/ai";
import { Link, useLocation, useNavigate } from 'react-router';
import { endSession, hasSession, subscribeSession } from "../../utils/session";

const Navbar = () => {
    const navigate = useNavigate(); // used by the logout button
    const location = useLocation();
    const [menuOpen, setMenuOpen] = useState(false);
    const closeMenu = () => setMenuOpen(false);
    const loggedIn = useSyncExternalStore(
        subscribeSession,
        () => hasSession(globalThis.localStorage),
        () => false,
    );

    // The session is removed only after the navigation to the login page has
    // committed. Clearing it first lets the page being left see a missing token
    // and redirect to "acesso negado" before the login page opens.
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
            <Link to="/" onClick={closeMenu}>LabTech UDF</Link>
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
        <Link className="nav-link active" to="/organizer" onClick={closeMenu}>
          <span className="nav-link-span">
            <span className="u-nav">Organizador</span>
          </span>
        </Link>
              {loggedIn && (
                <button type="button" id="logout" className="nav-link" onClick={logout}>
                  <span className="nav-link-span">
                    <span className="u-nav">Sair</span>
                  </span>
                </button>
              )}
            </div>
        </nav>
    );
}

export default Navbar;
