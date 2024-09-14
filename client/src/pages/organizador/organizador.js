import React, { useState } from 'react';
import './Organizador.scss';
import AvatarImage from '../../images/man.png';
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate } from 'react-router-dom'; // useNavigate para navegação
import axios from 'axios';

function Organizador() {
  const [email, setEmail] = useState("");
  const [errors, setErro] = useState("");
  const [loading, setLoading] = useState(false); // Adicionando estado de loading
  const navigate = useNavigate(); // Navegação por URL

  const handlerEmail = (event) => {
    setEmail(event.target.value);
  };

  const sendEmail = async (event) => {
    event.preventDefault();
    if (validEmail()) {
      setLoading(true);
      try{
        const response = await axios.post('http://127.0.0.1:5000/auth-mail', null,  {
          params: { email }
        });

        console.log(response.data)

        if (response.data.magic_link) {
          localStorage.setItem('userEmail', email);
          navigate('/confirmar-email');
        } else {
          setErro('Erro ao gerar o link.');
        }
      } catch (error){
        setErro(error.response?.data?.error || 'Erro ao enviar o e-mail.');
      } finally {
        setLoading(false);
      }
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
                  placeholder="Digite seu email@udf.edu.br"
                  value={email}
                  onChange={handlerEmail}
                  className="form-control"
              />
              {errors && <span style={{ color: 'red' }}>{errors}</span>}
              <div className="mt-4">
                <button type="submit" onClick={sendEmail} className="btn" disabled={loading}>
                  {loading ? 'Enviando...' : 'CONFIRMAR'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
  );
}

export default Organizador;
