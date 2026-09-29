import React, { createContext, useState, useContext } from 'react';

const PageContext = createContext();

export function PageProvider({ children }) {
    const [currentPage, setCurrentPage] = useState("Home");

    return (
        <PageContext.Provider value={{ currentPage, setCurrentPage }}>
            {children}
        </PageContext.Provider>
    )
}

export function usePage(){
    return useContext(PageContext);
}
