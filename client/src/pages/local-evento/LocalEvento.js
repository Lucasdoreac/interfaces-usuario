import React, { useState } from 'react';
import { Form } from 'react-router-dom';
import { AiOutlineLeft } from "react-icons/ai";

const LocalEvento = () => {
  // Define o estado inicial e a função para atualizar o estado
  const [dados, setDados]=useState(
    {
        numeroParticipantes:'',
        espacos:'', 

    }
    );
    const[erros, setErros]=useState(
        {
 
            
    });
    const handleChange = (e) => {
        const { name, value } = e.target;
        setDados({ ...dados, [name]: value });
    };

    const listaMonitores = ['Pedro', 'Lucas', 'Rafael'];
 
    const confLocalEvento = () => {

    }

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
          <div className="row">
            <div className="col">
                <label htmlFor="numeroParticipantes">Número de participantes</label>
                <input type= "number" className="form-control" min="0" max="100" id="numeroParticipantes" style={{width:200}} name='numeroParticipantes'></input>

            </div>

          </div><br></br>
          <div className="row">
            <div className='col'>
                <label htmlFor="espacos"> Espaços Necessários</label><br></br>

                <div className="form-check">
                        <input class="form-check-input" type="radio" name="espacos" id="online"  onChange={handleChange} value ='online' checked={dados.espacos === 'online'}></input>
                        <label class="form-check-label" for="online">
                            Online
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="espacos" id="auditorio"  onChange={handleChange} value ='auditorio' checked={dados.espacos === 'auditorio'}></input>
                        <label class="form-check-label" for="auditorio">
                            Auditório
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="espacos" id="hall"  onChange={handleChange} value ='hall' checked={dados.espacos === 'hall'}></input>
                        <label class="form-check-label" for="hall">
                            Hall
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="espacos" id="salaAula"  onChange={handleChange} value ='salaAula' checked={dados.espacos === 'salaAula'}></input>
                        <label class="form-check-label" for="salaAula">
                            Sala de Aula
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="espacos" id="laboratorioInfo"  onChange={handleChange} value ='laboratorioInfo' checked={dados.espacos === 'laboratorioInfo'}></input>
                        <label class="form-check-label" for="laboratorioInfo">
                            Laboratório de Informática
                        </label>
                    </div>

            </div>
          </div><br></br>
          <div className='row'>
            <div className='col-5'>
                <label for="trilha">Trilha empreendedora</label>
                <select id="trilha" name="trilha" value={dados.trilha} defaultValue="" onChange={handleChange} class="form-control"> 
                <option value="" disabled > </option>
                <option value='sim'>Sim</option>
                <option value='nao'>Não</option>
                </select>

            </div>
            <div className='col-7'>
            <label htmlFor="trilhaDesc">Se sim,digite aqui</label>
                    <input type= "text" className="form-control" id="trilhaDesc" name='trilhaDesc' value={dados.trilhaDesc} onChange={handleChange}/>
                    {erros.trilhaDesc && <span style={{ color: 'red' }}>{erros.trilhaDesc}</span>}

            </div>
          </div><br></br>
          <div className='row'>
            <div className='col-5'>
                <label for="projeto">Projeto Extensão</label>
                <select id="projeto" name="projeto" value={dados.projeto} defaultValue="" onChange={handleChange} class="form-control"> 
                <option value="" disabled > </option>
                <option value='sim'>Sim</option>
                <option value='nao'>Não</option>
                </select>
            

            </div>
            <div className='col-7'>
            <label htmlFor="projetoDesc">Se sim,digite aqui</label>
                    <input type= "text" className="form-control" id="projetoDesc" name='projetoDesc' value={dados.projetoDesc} onChange={handleChange}/>
                    {erros.projetoDesc && <span style={{ color: 'red' }}>{erros.projetoDesc}</span>}


            </div>
          </div>
<br></br>
        <div className='row'>
            <div className='col'>
            <label htmlFor="monitores">Alunos monitores</label>
            <select id="monitores" options={listaMonitores} name="monitores" isMulti value={dados.monitores} defaultValue="" onChange={handleChange} class="form-control" />

            </div>
            <div className='col'>
            <label htmlFor="logo">Logo do Evento</label>
                <input type='file' value={dados.logo} />

            </div>

        </div><br></br>
        <div className="row">
                        <div className="col">
                            <input type="button" className="btn btn-outline-secondary" value="Salvar Rascunho"/>
                            <button  type="button" className="btn btn-warning" onClick={confLocalEvento}>Próximo</button>
                    </div>
                </div>

        </div>
        </div>
      </div>
    </form>
   
  );
  
};

export default LocalEvento;