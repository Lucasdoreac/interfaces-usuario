import React from 'react';
import { Link } from 'react-router-dom';
import Button from '../components/Button/Button';
const Home = () =>{
  return (
    <div>
      <h1>Página Inicial</h1>
      <nav>
        <ul>
          <li>
            <Link to="/organizador">organizador</Link>
          </li>
          <li>
            <Button/>
          </li>
        </ul>
      </nav>
    </div>
  );
}

export default Home;