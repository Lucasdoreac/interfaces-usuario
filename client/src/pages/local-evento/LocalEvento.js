import React, { useState } from 'react';
import { Form } from 'react-router-dom';
import { AiOutlineLeft } from "react-icons/ai";

const LocalEvento = () => {
  // Define o estado inicial e a função para atualizar o estado
  const [mensagem, setMensagem] = useState('Olá, mundo!');

  // Função para mudar a mensagem
  const mudarMensagem = () => {
    setMensagem('Você clicou no botão!');
  };

  function handleSubmit(e) {
    e.preventDefault()
    console.log({data: e});
  }

  return (
    <form>
      <div>
        <div className="card-header">
        <div className="d-flex d-flex justify-content-start">
            <form onSubmit={handleSubmit}>
            </form> 
            <a href="/descricao-evento">
            <AiOutlineLeft
                      style={{
                        margin: "0px 10px 0px 0px"
                      }}
                      size="20px"
                      color="white"
                    />
                    </a>
                  <h5>Voltar Descrição Evento</h5>

            </div>
        </div>
        <div className="card-body">
        <div className="row"><div className="col-md-12"><h4>Novo Evento</h4></div></div>
        <div>
          <h1>{mensagem}</h1>
          <button onClick={mudarMensagem}>Clique aqui</button>
        </div>
        </div>
      </div>
    </form>
   
  );
  
};

export default LocalEvento;