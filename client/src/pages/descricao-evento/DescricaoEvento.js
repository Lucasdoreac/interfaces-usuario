import React, { useState } from "react";
import { AiOutlineLeft } from "react-icons/ai";
import './DescricaoEvento.scss';
import {useNavigate} from 'react-router-dom';

const DescricaoEvento=()=>{
    const navigate = useNavigate();

    const listaCurso = ['Ciência da Computação', 'Sistemas da Informação', 'Engenharia Civil'];
    const [dados, setDados]=useState(
        {
            linkEvento:'',
            descricaoEvento:'',
            curso:'',
            publicoAlvoRadio:'',
            recursosNecessariosRadio:'',

            

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
        
        if(validacaoDescricaoEvento()){
            navigate('/local-evento');

        }
    }

    const validacaoDescricaoEvento = ()=>{
        const erro = {};
        if(!dados.linkEvento.trim()){
            erro.linkEvento = "Campo obrigatório.";
            setErros(erro);
            return false;

        }
        if(!dados.descricaoEvento.trim()){
            erro.descricaoEvento = "Campo obrigatório.";
            setErros(erro);
            return false;

        }
        if(!dados.curso.trim()){
            erro.curso = "Campo obrigatório.";
            setErros(erro);
            return false;

        }
        if(!dados.publicoAlvoRadio.trim()){
            erro.publicoAlvoRadio = "Campo obrigatório.";
            setErros(erro);
            return false;

        }
        if(!dados.recursosNecessariosRadio.trim()){
            erro.recursosNecessariosRadio = "Campo obrigatório.";
            setErros(erro);
            return false;

        }
        

        return true;
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
                    {erros.linkEvento && <span style={{ color: 'red' }}>{erros.linkEvento}</span>}
                </div>
           </div>

           <div className="row">
              <div className="col">
                <label htmlFor="descricaoEvento"> Descrição do evento/ Objetivos</label>
                <input type="textArea" className="form-control" id="descricaoEvento" name="descricaoEvento" value={dados.descricaoEvento} onChange={handleChange}/>
                {erros.descricaoEvento && <span style={{ color: 'red' }}>{erros.descricaoEvento}</span>}
              </div>

           </div>
        
           <div className="row">
            <div className="col">
                    <label for="curso">Curso Vinculado</label>
                    <select id="curso" name="curso" value={dados.curso} defaultValue="" onChange={handleChange} class="form-control" style={{width:200}}>
                    <option value="" disabled > Nome curso e Código </option>

                      {
                        listaCurso.map((curso,index)=>(
                            <option value = {curso} key={index}>{curso}</option>
                        ))
                      }

                           
                    </select>

                    {erros.curso && <span style={{ color: 'red' }}>{erros.curso}</span>}
                </div>

            </div>
                    
           <div className="row">
                <div className="col">
                    <label htmlFor="publicoAlvo"> Público alvo</label><br></br>
                    
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="publicoAlvoRadio" id="alunosUDF"  onChange={handleChange} value ='alunosUDF' checked={dados.publicoAlvoRadio === 'alunosUDF'}></input>
                        <label class="form-check-label" for="alunosUDF">
                            Alunos UDF
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="publicoAlvoRadio" id="professores" onChange={handleChange} value ='professores' checked={dados.publicoAlvoRadio === 'professores'}></input>
                        <label class="form-check-label" for="professores">
                            Professores
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="publicoAlvoRadio" id="publicoExterno" onChange={handleChange} value ='publicoExterno' checked={dados.publicoAlvoRadio === 'publicoExterno'}></input>
                        <label class="form-check-label" for="publicoExterno">
                            Público externo
                        </label>
                    </div>
                    {erros.publicoAlvoRadio && <span style={{ color: 'red' }}>{erros.publicoAlvoRadio}</span>}
            </div>
        </div>

            <div className="row">
                <div className="col">
                    <label htmlFor="recursosNecessarios">Recursos Necessários</label><br></br>

                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="recursosNecessariosRadio" id="humanas" onChange={handleChange} value ='humanas' checked={dados.recursosNecessariosRadio === 'humanas'}></input>
                        <label class="form-check-label" for="flexRadioDefault1">
                            Humanas
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="recursosNecessariosRadio" id="tecnologias" onChange={handleChange} value ='tecnologias' checked={dados.recursosNecessariosRadio === 'tecnologias'}></input>
                        <label class="form-check-label" for="flexRadioDefault1">
                            Tecnologias
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="recursosNecessariosRadio" id="servicos" onChange={handleChange} value ='servicos' checked={dados.recursosNecessariosRadio === 'servicos'}></input>
                        <label class="form-check-label" for="flexRadioDefault1">
                            Serviços
                        </label>
                    </div>
                    <div className="form-check">
                        <input class="form-check-input" type="radio" name="recursosNecessariosRadio" id="materias" onChange={handleChange} value ='materias' checked={dados.recursosNecessariosRadio === 'materias'}></input>
                        <label class="form-check-label" for="flexRadioDefault1">
                            Materiais
                        </label>
                    </div>

                    {erros.recursosNecessariosRadio && <span style={{ color: 'red' }}>{erros.recursosNecessariosRadio}</span>}

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