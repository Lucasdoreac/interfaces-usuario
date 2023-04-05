import './App.css';
import {BrowserRouter, Routes, Route} from 'react-router-dom';
import Home from './pages/Home';
import Organizador from './pages/Organizador/Organizador';
import Navbar from './components/Navbar/Navbar';


function App() {
  return (
    <div className="App">
      <Navbar/>
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