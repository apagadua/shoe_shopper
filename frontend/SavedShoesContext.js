import React, { createContext, useContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'savedShoes';

const SavedShoesContext = createContext(null);

export function SavedShoesProvider({ children }) {
  const [savedMap, setSavedMap] = useState({});

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then(raw => { if (raw) setSavedMap(JSON.parse(raw)); })
      .catch(err => {
        console.error('Failed to load saved shoes:', err);
        setSavedMap({});
      });
  }, []);

  function toggleSaved(shoe) {
    if (!shoe?.id) return;
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

  const savedShoes = Object.values(savedMap);

  return (
    <SavedShoesContext.Provider value={{ savedMap, savedShoes, toggleSaved, isSaved }}>
      {children}
    </SavedShoesContext.Provider>
  );
}

export function useSavedShoes() {
  return useContext(SavedShoesContext);
}
