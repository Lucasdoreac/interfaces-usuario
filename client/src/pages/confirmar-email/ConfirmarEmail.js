import React from "react";
import AvatarImage from '../../images/man.png';
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
                    <img className="img-man mb-2" src={AvatarImage} style={{ width: '200px', }} alt="man avatar" />          
                  </div>
                </div>
              </div>
       </div>
    );
};

export default ConfirmarEmail;