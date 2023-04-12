import React from 'react';
import { Link } from 'react-router-dom';

const Organizador = () =>{
    return (
      <div>
        <h1>Página organizador</h1>
      
          <ul>
            <li>
              <Link to="/">home</Link>
            </li>
            <li>
              teste
            </li>
          </ul>
       
      </div>
    );
  }
  
  export default Organizador;