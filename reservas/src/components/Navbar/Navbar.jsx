import "./Navbar.scss";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { AiOutlineClose, AiOutlineMenu } from "react-icons/ai";
import { useLocation, useNavigate } from 'react-router';
import apiService from "../../services/client";
import { logoutNavigationState } from "../../utils/logoutNotice";
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

    // The server is told first (bounded, never throws), while the token is still stored; the local
    // session is then cleared by the effect above whether or not that call worked.
    const leaving = useRef(false);
    const logout = async () => {
        if (leaving.current) return;
        leaving.current = true;
        let confirmed = false;
        try {
            confirmed = (await apiService.logoutSession()) === true;
        } finally {
            leaving.current = false;
            // Sai sempre; se o servidor não confirmou, a tela de login avisa (sem repetir a chamada).
            go('/organizer', logoutNavigationState(confirmed));
        }
    };

    return (
        <nav id="nav" className={menuOpen ? "nav-visible" : undefined}>
            <div className="nav left">
        <span className="gradient skew">
          <h1 className="logo un-skew mt-4">
            <span onClick={() => go('/')}>LabTech UDF</span>
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
        <span className="nav-link active" onClick={() => go('/organizer')}>
          <span className="nav-link-span">
            <span className="u-nav">Organizador</span>
          </span>
        </span>
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
