import React from "react";
import {BrowserRoute, Switch, Route} from 'react-router-dom';

import Home from './pages/home';
import Organizador from './pages/organizador/route';
import Authorize from './page/autho'

const baseUrl = document.getElementsByTagName('base')[0].getAttribute('href');

// eslint-disable-next-line import/no-anonymous-default-export
export default () =>{
    return (
        <BrowserRoute baseUrl={baseUrl}>
            <Switch>
                <Route exact path="/" component={Authorize}/>                  
                <Route path="/home" component={Home}/>      
                {Organizador.map((x,index) => <Route key={index} exact path={x.path} component={x.component}/>)}
            </Switch>
       </BrowserRoute>
    )
}
