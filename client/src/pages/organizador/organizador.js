import React from 'react';
import { Link } from 'react-router-dom';

const Home = () =>{
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
  
  export default Home;