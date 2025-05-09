/* 
ThemeContext:  É o contexto que será usado para compartilhar o 
               estado do tema (Dark/Light) entre os componentes.
ThemeProvider: É o componente que gerencia o estado do tema e fornece
               esse estado e as funções relacionadas para os componentes filhos.
*/

import React, { createContext, useState} from 'react';

// Creat a context Theme
const ThemeContext = createContext()


//Creat a provider theme
const ThemeProvider = ({ children }) => {
    const getInitialTheme = () => {
         // Saves the theme choosen in localStorage.
        const savedTheme = localStorage.getItem('theme');
        if(savedTheme) {
            return savedTheme;
        }
        else{
            // If there is no theme saved in LS, uses Windows color preference.
            const windowsPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            return windowsPrefersDark ? 'dark' : 'light';
        }
            
    };
    const [theme, setTheme] = useState(getInitialTheme);
    
    const toggleTheme = () => {
        const newTheme = (theme === 'light') ? 'dark' : 'light';
        setTheme(newTheme);
        localStorage.setItem('theme', newTheme); //Store it in LocalStorage
    }

    return (
        // Information that will be shared with the components that are inside the provider.
        <ThemeContext.Provider value={{ theme, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}

export {ThemeContext, ThemeProvider};
