import React from 'react';
import { Navigate, useLocation } from 'react-router';
import { useFormContext } from './context/FormContext';
import PrivateRoute from './PrivateRoute';

/**
 * Componente que verifica se o tipo de evento permite acesso à rota
 * 
 * @param {Object} props - Propriedades do componente
 * @param {React.ComponentType} props.Component - O componente original a ser renderizado
 * @param {string[]} props.restrictedFor - Tipos de evento que NÃO podem acessar esta rota
 * @param {string} props.fallbackPath - Caminho para redirecionamento caso acesso negado
 * @returns {React.ReactElement} Componente ou redirecionamento
 */
const EventTypeChecker = ({ Component, restrictedFor = [], fallbackPath = "/event/type-selection" }) => {
  const { formData } = useFormContext();
  const location = useLocation();
  const eventType = formData?.classificacao || '';
  const queryParams = new URLSearchParams(location.search);
  const eventId = queryParams.get('eventId');
  
  // Se o tipo de evento estiver na lista de restritos, redireciona
  if (restrictedFor.includes(eventType)) {
    return <Navigate to={`${fallbackPath}${eventId ? `?eventId=${eventId}` : ''}`} replace />;
  }
  
  // Se passou pela verificação, renderiza o componente original
  return <Component />;
};

/**
 * Componente de rota que protege contra acesso baseado no tipo de evento
 * Mantém a proteção de autenticação do PrivateRoute e adiciona verificação de tipo
 * 
 * @param {Object} props - Propriedades do componente
 * @param {React.ComponentType} props.element - O componente a ser protegido
 * @param {string[]} props.restrictedFor - Tipos de evento que não podem acessar esta rota
 * @param {string} props.fallbackPath - Caminho para redirecionamento caso acesso negado
 * @returns {React.ReactElement} PrivateRoute com verificação adicional
 */
const EventTypeProtectedRoute = ({ element: Component, restrictedFor, fallbackPath, ...rest }) => {
  // Cria uma função que envolve o componente com o verificador
  const WrappedComponent = () => (
    <EventTypeChecker 
      Component={Component} 
      restrictedFor={restrictedFor} 
      fallbackPath={fallbackPath} 
    />
  );
  
  // Retorna um PrivateRoute usando o componente envolvido
  return <PrivateRoute element={WrappedComponent} {...rest} />;
};

export default EventTypeProtectedRoute;