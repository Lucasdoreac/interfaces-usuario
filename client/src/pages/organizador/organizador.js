import React, {useState} from 'react';
import './Organizador.scss';
import {useNavigate} from 'react-router-dom';
import AvatarImage from '../../images/man.png';
import { AiOutlineLeft } from "react-icons/ai";
// import axios from 'axios';
import '../../App.scss';

function Organizador(){

  const [email, setEmail] = useState("");

  const navigate = useNavigate();

  const handlerEmail = (event)=> {
    setEmail(event.target.value);
  };
  const sendEmail =(event) =>{
    // Faz a requisição POST com o valor do email
    event.preventDefault();
    console.log("entrou teste 1 "+email);
    navigate('/confirmar-email');


  };


  return (
    <div>
      <div className="card-header">
                <div className="d-flex d-flex justify-content-start">
                  <a href="/">
                    <AiOutlineLeft
                      style={{
                        margin: "0px 10px 0px 0px"
                      }}
                      size="20px"
                      color="white"
                    />
                  </a>
                  <h5>Voltar</h5>
                </div>
              </div>
              <div className="card-body">
                <div className="row">
                  <div className="col-md-12 text-center">
                    <img className="img-man mb-2" src={AvatarImage} style={{ width: '200px', }} alt="man avatar" />
                    
                      <input  type="email"   placeholder="Digite seu email@aluno.cruzeirodosul.edu.br"  value={email}  onChange={handlerEmail}  className="form-control "  />                
                          
                      <div className="mt-4">
                        <button type="submit" onClick={sendEmail} className="btn"  size="md" text="CONFIRMAR" >CONFIRMAR  </button>

                      </div>
                          
                  </div>
                </div>
              </div>
    </div>
  );
}

export default Organizador;