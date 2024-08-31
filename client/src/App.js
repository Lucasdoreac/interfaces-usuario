import './App.scss';
import {BrowserRouter, Routes, Route} from 'react-router-dom';
import Home from './pages/Home/Home';
import Organizador from './pages/organizador/organizador';
import Navbar from './components/Navbar/Navbar';
import 'bootstrap/dist/css/bootstrap.min.css';
import ConfirmarEmail from './pages/confirmar-email/ConfirmarEmail';


function App() {
  return (
    <div className="App">
      {/* <Navbar/> */}
      <section id="paginaInicial" className="section-padding">
        <div className='container'>
          <div className='row justify-content-center'>
            <div className='col-md-6'>
              <div className='card'>
              <BrowserRouter>      
                <Routes>
                  <Route path='/' element={<Home/>} />
                  <Route path='/organizador' element={<Organizador/>} />
                  <Route path='/confirmar-email' element={<ConfirmarEmail/>} />
                </Routes>
              </BrowserRouter>
              </div>
            </div>
          </div>      
        </div>      
      </section>  
    </div>
  );
}

export default App;