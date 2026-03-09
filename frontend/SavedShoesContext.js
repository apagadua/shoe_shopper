import React, { createContext, useContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'savedShoes';

const SavedShoesContext = createContext(null);

export function SavedShoesProvider({ children }) {
  const [savedMap, setSavedMap] = useState({});

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then(raw => { if (raw) setSavedMap(JSON.parse(raw)); })
      .catch(() => {});
  }, []);

  function toggleSaved(shoe) {
    setSavedMap(prev => {
      const next = { ...prev };
      if (next[shoe.id]) {
        delete next[shoe.id];
      } else {
        next[shoe.id] = shoe;
      }
      AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next)).catch(() => {});
      return next;
    });
  }

  function isSaved(id) {
    return Boolean(savedMap[id]);
  }

  return (
    <SavedShoesContext.Provider value={{ savedMap, toggleSaved, isSaved }}>
      {children}
    </SavedShoesContext.Provider>
  );
}

export function useSavedShoes() {
  return useContext(SavedShoesContext);
}
