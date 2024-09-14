import React, { useState } from 'react';
import './Organizador.scss';
import AvatarImage from '../../images/man.png';
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate } from 'react-router-dom'; // useNavigate para navegação

function Organizador() {
  const [email, setEmail] = useState("");
  const [errors, setErro] = useState("");
  const navigate = useNavigate(); // Navegação por URL

  const handlerEmail = (event) => {
    setEmail(event.target.value);
  };

  const sendEmail = (event) => {
    event.preventDefault();
    if (validEmail()) {
      // Lógica de envio de email...
      navigate('/confirmar-email'); // Navegar para /confirmar-email
    }
  };

  const validEmail = () => {
    if (!email.trim()) {
      setErro("O campo e-mail é obrigatório.");
      return false;
    }

    if (!/^[a-zA-Z0-9._%+-]+@udf\.edu\.br$/.test(email)) {
      setErro("O campo e-mail está fora do formato permitido.");
      return false;
    }

    return true;
  };

  return (
      <div>
        <div className="card-header">
          <div className="d-flex justify-content-start">
          <span onClick={() => navigate('/')}>
            <AiOutlineLeft size="20px" color="white" style={{ margin: "0px 10px 0px 0px" }} />
          </span>
            <h5>Voltar</h5>
          </div>
        </div>
        <div className="card-body">
          <div className="row">
            <div className="col-md-12 text-center">
              <img className="img-man mb-2" src={AvatarImage} style={{ width: '200px' }} alt="man avatar" />
              <input
                  type="email"
                  placeholder="Digite seu email@aluno.cruzeirodosul.edu.br"
                  value={email}
                  onChange={handlerEmail}
                  className="form-control"
              />
              {errors && <span style={{ color: 'red' }}>{errors}</span>}
              <div className="mt-4">
                <button type="submit" onClick={sendEmail} className="btn">CONFIRMAR</button>
              </div>
            </div>
          </div>
        </div>
      </div>
  );
}

export default Organizador;
