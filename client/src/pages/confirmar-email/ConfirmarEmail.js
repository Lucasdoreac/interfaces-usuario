import React, { useEffect, useState } from "react";
import EnvImage from '../../images/email.png';
import { AiOutlineLeft } from "react-icons/ai";
import './ConfirmarEmail.scss';
import { useNavigate } from 'react-router-dom';

const ConfirmarEmail = () => {
    const navigate = useNavigate();
    const [email, setEmail] = useState("");

    useEffect(() => {
        const userEmail = localStorage.getItem('userEmail');
        if (userEmail) {
            setEmail(userEmail);
        } else {
            navigate('/organizador');
        }
    }, [navigate]);

    const emailConfirmado = () =>{
        navigate('/dados-pessoais');
    }

    return (
        <div>
            <div className="card-header">
                <div className="d-flex d-flex justify-content-start">
          <span onClick={() => navigate('/organizador')}>
            <AiOutlineLeft
                style={{
                    margin: "0px 10px 0px 0px"
                }}
                size="20px"
                color="white"
            />
          </span>
                    <h5>Voltar</h5>
                </div>
            </div>
            <div className="card-body">
                <div className="row">
                    <div className="col-md-12 text-center">
                        <img className="img-man mb-2" src={EnvImage} style={{ width: '200px', backgroundColor: 'transparent' }} alt="man avatar" />
                        <p>Clique no link do e-mail que enviamos para <b>{email}</b></p> {/* Mostra o e-mail correto */}
                        <div className="mt-4">
                            <button type="submit" className="btn" onClick={emailConfirmado}>
                                CONFIRMADO
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ConfirmarEmail;
