import React, { useState } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import './DescricaoEvento.scss';
import {useNavigate} from 'react-router-dom';

const DescricaoEvento=()=>{
    const navigate = useNavigate();
    const [dados, setDados]=useState(
        {
            linkEvento:'',
            descricaoEvento:'',
            

        }
    );
    const[erros, setErros]=useState(
        {
            linkEvento:'',
            descricaoEvento:'',
            
    });

    const handleChange = (e) => {
        const { name, value } = e.target;
        setDados({ ...dados, [name]: value });
    };
    function handleSubmit(e) {
        e.preventDefault()
        console.log({data: e});
    }
    const confDescricaoEventos = ()=>{
        navigate('/local-evento');
    }

    return (
        <form>
        <div>
           <div className="card-header">
            <div className="d-flex d-flex justify-content-start">
            <form onSubmit={handleSubmit}>
            </form> 
            <a href="/dados-pessoais">
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
                    <label htmlFor="linkEvento">Link do evento/Inscrições</label>
                    <input type= "text" className="form-control" id="linkEvento" name='linkEvento' value={dados.linkEvento} onChange={handleChange}/>

                </div>
           </div>

           <div className="row">
              <div className="col">
                <label htmlFor="descricaoEvento"> Descrição do evento/ Objetivos</label>
                <input type="textArea" className="form-control" id="descricaoEvento" name="descricaoEvento" value={dados.descricaoEvento} onChange={handleChange}/>
               
              </div>

           </div>
        
           <div className="row">
           <div className="col">
                <label for="inputState">Curso Vinculado</label><select id="inputState" class="form-control" style={{width:200}}>
                         <option selected>Nome curso e código</option>
                         <option>...</option>
                            </select>
                        </div>

                       </div>
                    
           <div className="row">
                <div className="col">
                    <label htmlFor="publicoAlvo"> Público alvo</label><br></br>
                    
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="publicoAlvoRadio" id="alunosUDF"></input>
                        <label class="form-check-label" for="flexRadioDefault1">
                            Alunos UDF
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="publicoAlvoRadio" id="professores"></input>
                        <label class="form-check-label" for="flexRadioDefault2">
                            Professores
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="publicoAlvoRadio" id="publicoExterno"></input>
                        <label class="form-check-label" for="flexRadioDefault3">
                            Público externo
                        </label>
                    </div>
                    
            </div>
        </div>

            <div className="row">
                <div className="col">
                    <label htmlFor="recursosNecessarios">Recursos Necessários</label><br></br>

                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="recursosNecessariosRadio" id="humanas"></input>
                        <label class="form-check-label" for="flexRadioDefault1">
                            Humanas
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="recursosNecessariosRadio" id="tecnologias"></input>
                        <label class="form-check-label" for="flexRadioDefault1">
                            Tecnologias
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="recursosNecessariosRadio" id="servicos"></input>
                        <label class="form-check-label" for="flexRadioDefault1">
                            Serviços
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="recursosNecessariosRadio" id="materias"></input>
                        <label class="form-check-label" for="flexRadioDefault1">
                            Materiais
                        </label>
                    </div>

                    <br/>
                    <div className="row">
                        <div className="col">
                            <input type="button" className="btn btn-outline-secondary" value="Salvar Rascunho"/>
                            <button  type="button" className="btn btn-warning" onClick={confDescricaoEventos}>Próximo</button>
                    </div>
                </div>

                </div>
                </div>          

    
         </div>
        </div >

        </form>
    );
    
}
export default DescricaoEvento;