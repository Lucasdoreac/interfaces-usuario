import React, { useState } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import './DadosPessoais.scss';
import {useNavigate} from 'react-router-dom';
import InputMask from 'react-input-mask';

const DadosPessoais=()=>{
    const navigate = useNavigate();

    const listaTpEvento=['tipo evento 1', 'tipo evento 2', 'tipo evento 3'];

    const listaHorario=['de 08:00 a 10:00', 'de 14:00 a 15:00', 'de 16:00 a 17:00'];

    const listaODS=['1 a 17', '17 a 34']; 

    const [dados, setDados]=useState(
        {
            tituloEvento:'',
            nomeProfessor:'',
            emailProfessor:'',
            telefone:'',
            classificacao:'', 
            horario:'',
            ods:'',

        }
    );
    const[erros, setErros]=useState( {

    });

    const handleChange = (e) => {
        const { name, value } = e.target;
        setDados({ ...dados, [name]: value });
    };

    const confDadosPessoais = ()=>{
        if(validaFormulario()){
            navigate('/descricao-evento');
        }
        
    }

    const validaFormulario = () =>{
        const erro = {};
        if(!dados.tituloEvento.trim()){
            
            erro.tituloEvento = "O campo nome do evento é obrigatório.";
            setErros(erro); 
            return false;

        }
        if(dados.tituloEvento.length<5){

            erro.tituloEvento = "O campo nome do evento precisa ter mais caracteres!";
            setErros(erro);
            return false;
        }
        if(!dados.nomeProfessor.trim()){

            erro.nomeProfessor = "O campo PROFESSOR é obrigatório.";
            setErros(erro); 
            return false;

        }
        if(!dados.telefone.trim()){

            erro.telefone = "O número de telefone é obrigatório.";
            setErros(erro);
            return false;
        }
        if(!dados.classificacao.trim()){

            erro.classificacao = "Defina uma classificação.";
            setErros(erro);
            return false; 

        }
        if(!dados.horario.trim()){

            erro.horario = "E necessário definir um horário.";
            setErros(erro);
            return false;
        }
        if(!dados.ods.trim()){

            erro.ods = "Defina uma ODS.";
            setErros(erro);
            return false;
        }


        return true; 

    }; 

    const [startDate, setStartDate] = useState(new Date());

    return (
        <form>
        <div>
             <div className="card-header">
                <div className="d-flex d-flex justify-content-start">
                  <a href="/confirmar-email">
                    <AiOutlineLeft
                      style={{
                        margin: "0px 10px 0px 0px"
                      }}
                      size="20px"
                      color="white"
                    />
                  </a>
                  <h5>X Cancelar</h5>
                </div>
              </div>
              <div className="card-body">
                <div className="row"><div className="col-md-12"><h4>Novo Evento</h4></div></div>

                <div className="row">
                    <div className="col">
                            <label htmlFor="formTitulo">Nome do Evento</label>
                            <input type= "text" className="form-control" id="formTitulo" name='tituloEvento' value={dados.tituloEvento} onChange={handleChange}/>
                            {erros.tituloEvento && <span style={{ color: 'red' }}>{erros.tituloEvento}</span>}
                    </div>
             
                </div> 
                <div className="row">
                        <div className="col">
                            <label htmlFor = "formProfessor">Professor</label>
                            <input type= "text" className="form-control" id="formProfessor" name="nomeProfessor" value={dados.nomeProfessor} onChange={handleChange} />
                            {erros.nomeProfessor && <span style={{ color: 'red' }}>{erros.nomeProfessor}</span>}
                        </div>
                </div>
                {/*<div className="row">
                        <div className="col">
                            <label htmlFor = "formEmail">E-mail</label>
                            <input type= "text" className="form-control" id="formEmail" name="emailProfessor" value={dados.emailProfessor} onChange={handleChange} />

                        </div>
                </div>*/}
                <div className="row">
                        <div className="col">
                            <label htmlFor="telefone">Telefone</label>
                        
                            <InputMask mask="(99)9 9999-9999" id="telefone" name="telefone" placeholder="(XX) XXXXX-XXXX" value={dados.telefone} onChange={handleChange}>
                                {(inputProps) =><input {...inputProps} type="text" className="form-control" style={{width:200}}/>}
                            </InputMask>
                            {erros.telefone && <span style={{ color: 'red' }}>{erros.telefone}</span>}

                        </div>

                        <div className="col">
                        <label htmlFor="classificacao">Classificação</label>
                        <select class="form-control" style={{width:150}} defaultValue="" onChange={handleChange} value = {dados.classificacao}  id="classificacao" name="classificacao" >
                                <option value="" disabled > Tipo do Evento </option>

                                {
                                  listaTpEvento.map((evt,index)=>(
                                     <option value = {evt} key={index}>{evt}</option>
                                    ))
                                }
                            </select>
                            {erros.classificacao && <span style={{ color: 'red' }}>{erros.classificacao}</span>}
                        </div>
                        
                </div> 
               <div className="row">
                    {/* <div className="col">
                        <label htmlFor="date">Data do evento</label>
                        <select id="inputState" defaultValue = "" class="form-control" style={{width:150}}>
                            <option selected>Data</option>
                            <option selected={startDate}>...</option>
                        </select>
                    </div> */}

                    <div className="col">
                            <label htmlFor="horario">Horário</label>
                            <select id="horario" name="horario" class="form-control" style={{width:200}} defaultValue="" onChange={handleChange} value = {dados.horario} >

                                <option value ="" disabled>de HH:MM a HH:MM</option>

                                {
                                    listaHorario.map((hr,index)=>(
                                        <option value={hr} key={index}>{hr}</option>
                                    ))
                                }

                            </select>

                            {erros.horario && <span style={{ color: 'red' }}>{erros.horario}</span>}
                        </div>
                    <div> 
                    <div className="col">
                            <label htmlFor="ods">Classificação ODS</label>
                            <select id="ods" name="ods" class="form-control" style={{width:150}} defaultValue="" onChange={handleChange} value={dados.ods}>
                                
                                <option value="" disabled>ODS</option>

                                {
                                    listaODS.map((ods, index)=>(
                                        <option value={ods} key={index}>{ods}</option>
                                    ))
                                }
                            </select>
                            {erros.ods && <span style={{ color: 'red' }}>{erros.ods}</span>}
                        </div>
                       
                    </div>

            
                </div>
                <br/>
                <div className="row">
                    <div className="col">
                        <input type="button" className="btn btn-outline-secondary" value="Salvar Rascunho"/>
                        <button  type="button" className="btn btn-warning" onClick={confDadosPessoais}>Próximo</button>
                    </div>
                </div>
                

              </div>
        </div>
        </form>
    );
};

export default DadosPessoais;