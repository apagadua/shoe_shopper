/**
 * Wishlist state: shoes heart-saved from Recommendations. Persisted in AsyncStorage only
 * (not synced to backend UserCollection). See FRONTEND_FEATURES.md §8.
 */
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
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

  const toggleSaved = useCallback((shoe) => {
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
  }, []);

  const isSaved = useCallback((id) => Boolean(savedMap[id]), [savedMap]);

  const savedShoes = useMemo(() => Object.values(savedMap), [savedMap]);

  const contextValue = useMemo(
    () => ({ savedMap, savedShoes, toggleSaved, isSaved }),
    [savedMap, savedShoes, toggleSaved, isSaved]
  );

  return (
    <SavedShoesContext.Provider value={contextValue}>
      {children}
    </SavedShoesContext.Provider>
  );
}

export function useSavedShoes() {
  return useContext(SavedShoesContext);
}
