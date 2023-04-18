import React, { useState } from 'react';
import './Organizador.scss';
import Input from '../../components/Input/Input';
import AvatarImage from '../../images/man.png';

import ApiService from '../../services/client';

const Organizador = () => {
  const [email, setEmail] = useState('');

  const handleSubmit = async (e) => {
    // e.preventDefault();
    if (email && email.endsWith('@udf.edu.br')) {
      try {
        const response = await ApiService.postAuthMail(email);
        console.log(response.data);
      } catch (error) {
        console.error(error);
      }
    } else {
      console.error('Invalid email address');
    }
  };

  const handleChange = (e) => {
    setEmail(e.target.value);
  };


  return (
    <section id="organizador" className="section-padding">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-md-6">
            <div className="card">
              <div className="card-header">
                <div className="row justify-content-center">
                  <div className="col-md-6">
                    <h5>Organizador</h5>
                  </div>
                </div>
              </div>
              <div className="card-body">
                <div className="row">
                  <div className="col-md-12 text-center">
                    <img className="img-man" src={AvatarImage} style={{ width: '200px', }} alt="man avatar" />
                    <div className="mt-4">
                      <Input type="input-text" placeholder="Digite o e-mail para cadastro" onChange={handleChange}/>
                      <button onClick={() => handleSubmit()}>
                        Request Auth Mail
                      </button>
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