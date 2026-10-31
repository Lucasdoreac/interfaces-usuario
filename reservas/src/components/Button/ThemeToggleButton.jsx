// Component responsible for the theme toggle button
/*
O que ele fará?
Consumirá o ThemeContext para acessar: o tema atual e a função de toggleTheme
para alternar entre os temas light e dark.
*/
import React, {useContext} from 'react';
import { ThemeContext } from '../../context/ThemeContext';
import './ThemeToggleButton.scss'; 



const ThemeToggleButton = () => {
    const { theme, toggleTheme } = useContext(ThemeContext);

    return (
        <div className = "toggle-button-container" >
    
            {/* Changes the css personalization acording to theme displayed*/}
            <button 
                className = {'toggle-button ' + theme} 
                onClick={toggleTheme}>
                
                {theme === 'light'? 'Switch to Dark Mode' : 'Switch to Light Mode'}
            </button>
        </div>
    )

}
export default ThemeToggleButton;
