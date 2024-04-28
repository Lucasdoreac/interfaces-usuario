import React from "react";
import EnvImage from '../../images/email.png';
import { AiOutlineLeft } from "react-icons/ai";
import './ConfirmarEmail.scss';


const ConfirmarEmail = () =>{


  
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
                    <img className="img-man mb-2" src={EnvImage} style={{ width: '200px',backgroundColor: 'transparent' }} alt="man avatar" />
                    <p>Clique no link do e-mail que enviamos para <b>organizador@udf.edu.br</b></p>
                    <div className="mt-4">
                        <button type="submit" className="btn"  size="md" text="CONFIRMADO" >CONFIRMADO </button>
                      </div>       
                  </div>
                </div>
              </div>
       </div>
    );
};

export default ConfirmarEmail;