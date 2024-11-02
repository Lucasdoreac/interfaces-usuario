import React from 'react';
import './Home.scss';
import AvatarImage from '../../images/man.png';
import { useNavigate } from 'react-router-dom'; // Importar useNavigate para navegação

const Home = () => {
    const navigate = useNavigate(); // Usar useNavigate para navegação entre páginas

    return (
        <div>
            <div className="card-header">
                <div className="row mb-4">
                    <div className="col-md-3">
                        {/* Espaço vazio */}
                    </div>
                </div>
            </div>
            <div className="card-body">
                <div className="row">
                    <div className="col-md-12 text-center">
                        <img
                            className="img-man"
                            src={AvatarImage}
                            style={{ width: '200px' }}
                            alt="man avatar"
                        />
                        <div className="mt-4">
                            {/* O botão agora usa onClick para navegação */}
                            <button
                                className="btn"
                                size="md"
                                onClick={() => navigate('/organizador')} // Navegar para a página "Organizador"
                            >
                                ORGANIZADOR
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Home;
