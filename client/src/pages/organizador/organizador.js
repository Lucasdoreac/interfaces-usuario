import React from 'react';
import './Organizador.scss';
import Input from '../../components/Input/Input';
import AvatarImage from '../../images/man.png';
const Organizador = () =>{
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
                     <img className="img-man" src={AvatarImage} style={{ width: '200px', }} alt="man avatar"/>  
                       <div className="mt-4">                    
                         <Input  type="input-text" placeholder="Digite o e-mail para cadastro"/>
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