import React, { createContext, useContext, useEffect, useState } from 'react';

const ThemeContext = createContext();

export const ThemeProvider = ({ children }) => {
  const [activeColorTheme] = useState('blue');

  useEffect(() => {
    const root = document.documentElement;
    const body = document.body;
    root.classList.add('theme-blue');
    root.classList.remove('theme-pink');
    body.classList.add('theme-blue');
    body.classList.remove('theme-pink');
  }, []);

  return (
    <ThemeContext.Provider value={{ activeColorTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);
