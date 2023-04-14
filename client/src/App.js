import './App.scss';
import {BrowserRouter, Routes, Route} from 'react-router-dom';
import Home from './pages/Home/Home';
import Organizador from './pages/Organizador/Organizador';
import Navbar from './components/Navbar/Navbar';
import 'bootstrap/dist/css/bootstrap.min.css';


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