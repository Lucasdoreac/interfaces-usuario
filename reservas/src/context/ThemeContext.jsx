/* 
ThemeContext:  É o contexto que será usado para compartilhar o 
               estado do tema (Dark/Light) entre os componentes.
ThemeProvider: É o componente que gerencia o estado do tema e fornece
               esse estado e as funções relacionadas para os componentes filhos.
*/

import React, { createContext, useEffect, useState} from 'react';

// Creat a context Theme
const ThemeContext = createContext()


//Creat a provider theme
const ThemeProvider = ({ children }) => {
    const [theme, setTheme] = useState('light');

    useEffect(() => {
        const savedTheme = window.localStorage.getItem('theme');
        setTheme(savedTheme === 'dark' || savedTheme === 'light'
            ? savedTheme
            : window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    }, []);

    useEffect(() => {
        document.body.classList.toggle('dark', theme === 'dark');
        document.body.classList.toggle('light', theme === 'light');
        document.body.classList.toggle('dark-theme', theme === 'dark');
    }, [theme]);
    
    const toggleTheme = () => {
        const newTheme = (theme === 'light') ? 'dark' : 'light';
        setTheme(newTheme);
        window.localStorage.setItem('theme', newTheme); //Store it in LocalStorage
    }

    return (
        // Information that will be shared with the components that are inside the provider.
        <ThemeContext.Provider value={{ theme, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}

export {ThemeContext, ThemeProvider};
