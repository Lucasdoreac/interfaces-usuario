import React from 'react';
import { Link } from 'react-router-dom';

const Organizador = () =>{
    return (
      <div>
        <h1>Página organizador</h1>
        <nav>
          <ul>
            <li>
              <Link to="/">home</Link>
            </li>
            <li>
              teste
            </li>
          </ul>
        </nav>
      </div>
    );
  }
  
  export default Organizador;