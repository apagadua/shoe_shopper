import React, { createContext, useContext, useMemo, useState } from 'react';

const SavedShoesContext = createContext({
  savedShoes: [],
  toggleSaved: (_shoe) => {},
  isSaved: (_id) => false,
});

export function SavedShoesProvider({ children }) {
  const [savedShoes, setSavedShoes] = useState([]);

  const toggleSaved = (shoe) => {
    if (!shoe || !shoe.id) return;
    setSavedShoes((prev) => {
      const exists = prev.some((s) => s.id === shoe.id);
      if (exists) {
        return prev.filter((s) => s.id !== shoe.id);
      }
      return [...prev, shoe];
    });
  };

  const isSaved = (id) => savedShoes.some((s) => s.id === id);

  const value = useMemo(
    () => ({
      savedShoes,
      toggleSaved,
      isSaved,
    }),
    [savedShoes],
  );

  return <SavedShoesContext.Provider value={value}>{children}</SavedShoesContext.Provider>;
}

export function useSavedShoes() {
  return useContext(SavedShoesContext);
}

