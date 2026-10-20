import React from 'react';
import { usePage } from '../../context/PageProvider';
import Home from '../../pages/Home/Home';
import Organizador from '../../pages/organizador/organizador';
import ConfirmarEmail from '../../pages/confirmar-email/ConfirmarEmail';
import DadosPessoais from '../../pages/dados-pessoais/DadosPessoais';
import DescricaoEvento from '../../pages/descricao-evento/DescricaoEvento';
import LocalEvento from '../../pages/local-evento/LocalEvento';

function PageContent() {
    const { currentPage } = usePage();

    switch (currentPage) {
        case 'Home':
            return <Home />;
        case 'Organizador':
            return <Organizador />;
        case 'ConfirmarEmail':
            return <ConfirmarEmail />;
        case 'DadosPessoais':
            return <DadosPessoais />;
        case 'DescricaoEvento':
            return <DescricaoEvento />;
        case 'LocalEvento':
            return <LocalEvento />;
        default:
            return <Home />;
    }
}

export default PageContent;
