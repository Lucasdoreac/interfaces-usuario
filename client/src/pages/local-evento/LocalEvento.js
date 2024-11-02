import React, { useState } from 'react';
import { AiOutlineLeft } from "react-icons/ai";
import { useNavigate } from 'react-router-dom';

const LocalEvento = () => {
    const navigate = useNavigate();

    const [dados, setDados]=useState({
        numeroParticipantes:'',
        espacos:'',
    });

    const handleChange = (e) => {
        const { name, value } = e.target;
        setDados({ ...dados, [name]: value });
    };

    const listaMonitores = ['Pedro', 'Lucas', 'Rafael'];

    const confLocalEvento = () => {
        navigate('/proximo-passo'); // Exemplo de navegação
    }

    return (
        <form>
            <div>
                <div className="card-header">
                    <div className="d-flex d-flex justify-content-start">
            <span onClick={() => navigate('/descricao-evento')}>
              <AiOutlineLeft
                  style={{ margin: "0px 10px 0px 0px" }}
                  size="20px"
                  color="white"
              />
            </span>
                        <h5>Voltar Descrição Evento</h5>
                    </div>
                </div>
                <div className="card-body">
                    <div className="row"><div className="col-md-12"><h4>Novo Evento</h4></div></div>
                    <div className="row">
                        <div className="col">
                            <label htmlFor="numeroParticipantes">Número de participantes</label>
                            <input type="number" className="form-control" min="0" max="100" id="numeroParticipantes" style={{width:200}} name='numeroParticipantes' value={dados.numeroParticipantes} onChange={handleChange}></input>
                        </div>
                    </div>
                    <br/>
                    <div className="row">
                        <div className='col'>
                            <label htmlFor="espacos">Espaços Necessários</label><br/>
                            <div className="form-check">
                                <input className="form-check-input" type="radio" name="espacos" id="online" onChange={handleChange} value="online" checked={dados.espacos === 'online'} />
                                <label className="form-check-label" htmlFor="online">Online</label>
                            </div>
                            <div className="form-check">
                                <input className="form-check-input" type="radio" name="espacos" id="auditorio" onChange={handleChange} value="auditorio" checked={dados.espacos === 'auditorio'} />
                                <label className="form-check-label" htmlFor="auditorio">Auditório</label>
                            </div>
                            <div className="form-check">
                                <input className="form-check-input" type="radio" name="espacos" id="hall" onChange={handleChange} value="hall" checked={dados.espacos === 'hall'} />
                                <label className="form-check-label" htmlFor="hall">Hall</label>
                            </div>
                            <div className="form-check">
                                <input className="form-check-input" type="radio" name="espacos" id="salaAula" onChange={handleChange} value="salaAula" checked={dados.espacos === 'salaAula'} />
                                <label className="form-check-label" htmlFor="salaAula">Sala de Aula</label>
                            </div>
                            <div className="form-check">
                                <input className="form-check-input" type="radio" name="espacos" id="laboratorioInfo" onChange={handleChange} value="laboratorioInfo" checked={dados.espacos === 'laboratorioInfo'} />
                                <label className="form-check-label" htmlFor="laboratorioInfo">Laboratório de Informática</label>
                            </div>
                        </div>
                    </div>
                    <br/>
                    <div className='row'>
                        <div className='col-5'>
                            <label htmlFor="trilha">Trilha empreendedora</label>
                            <select id="trilha" name="trilha" value={dados.trilha} defaultValue="" onChange={handleChange} className="form-control">
                                <option value="" disabled></option>
                                <option value='sim'>Sim</option>
                                <option value='nao'>Não</option>
                            </select>
                        </div>
                        <div className='col-7'>
                            <label htmlFor="trilhaDesc">Se sim, digite aqui</label>
                            <input type="text" className="form-control" id="trilhaDesc" name="trilhaDesc" value={dados.trilhaDesc} onChange={handleChange}/>
                        </div>
                    </div>
                    <br/>
                    <div className='row'>
                        <div className='col-5'>
                            <label htmlFor="projeto">Projeto Extensão</label>
                            <select id="projeto" name="projeto" value={dados.projeto} defaultValue="" onChange={handleChange} className="form-control">
                                <option value="" disabled></option>
                                <option value='sim'>Sim</option>
                                <option value='nao'>Não</option>
                            </select>
                        </div>
                        <div className='col-7'>
                            <label htmlFor="projetoDesc">Se sim, digite aqui</label>
                            <input type="text" className="form-control" id="projetoDesc" name="projetoDesc" value={dados.projetoDesc} onChange={handleChange}/>
                        </div>
                    </div>
                    <br/>
                    <div className="row">
                        <div className="col">
                            <input type="button" className="btn btn-outline-secondary" value="Salvar Rascunho"/>
                            <button  type="button" className="btn btn-warning" onClick={confLocalEvento}>Próximo</button>
                        </div>
                    </div>
                </div>
            </div>
        </form>
    );
};

export default LocalEvento;
