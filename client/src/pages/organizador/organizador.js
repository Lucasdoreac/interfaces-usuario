import React, { useState } from 'react';
import './Organizador.scss';
import Input from '../../components/Input/Input';
import AvatarImage from '../../images/man.png';
import { AiOutlineLeft } from "react-icons/ai";
import Button from '../../components/Button/Button';
import axios from 'axios';
import mask from 'remask';
import '../../App.scss';
const Organizador = () => {

  const [email, setEmail] = useState('');
 

  const sendEmail = (email) => {
    // Faz a requisição POST com o valor do email
    axios.post('URL_DA_API', { email: email })
      .then((response) => {
        // Lógica de sucesso
        console.log(response.data)
      })
      .catch((error) => {
        // Lógica de erro
      });
  };
  
  return (
    <section id="organizador" className="section-padding">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-md-6">
            <div className="card">
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
                    
                          <Input
                          type="email"    
                          placeholder="Digite seu email@aluno.cruzeirodosul.edu.br"
                          className="form-control " // Aplica o estilo da máscara
                          />                    
                          <div className="mt-4">
                            <Button onClick={sendEmail} className="btn"  size="md" text="CONFIRMAR" />
                            
                          </div>
                  
                  
                   
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>


    </section>
  );
}

export default Organizador;