import './App.css';
import {BrowserRouter, Routes, Route} from 'react-router-dom';
import Home from './pages/home';
import Organizador from './pages/organizador/organizador'
function App() {
  return (
    <div className="App">
    {/* navbar aqui  */}

      <BrowserRouter>      
        <Routes>
          <Route path='/' element={<Home/>} />
          <Route path='/organizador' element={<Organizador/>} />
        </Routes>
    
      </BrowserRouter>
     
    </div>
  );
}

export default App;