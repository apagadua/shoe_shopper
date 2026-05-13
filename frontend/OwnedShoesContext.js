import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'ownedShoes';

const OwnedShoesContext = createContext(null);

export function OwnedShoesProvider({ children }) {
  const [ownedMap, setOwnedMap] = useState({});

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((raw) => {
        if (raw) setOwnedMap(JSON.parse(raw));
      })
      .catch(() => setOwnedMap({}));
  }, []);

  const toggleOwned = useCallback((shoe) => {
    if (!shoe?.id) return;
    setOwnedMap((prev) => {
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

  const isOwned = useCallback((id) => Boolean(ownedMap[id]), [ownedMap]);

  const ownedShoes = useMemo(() => Object.values(ownedMap), [ownedMap]);

  const contextValue = useMemo(
    () => ({ ownedMap, ownedShoes, toggleOwned, isOwned }),
    [ownedMap, ownedShoes, toggleOwned, isOwned]
  );

  return (
    <OwnedShoesContext.Provider value={contextValue}>
      {children}
    </OwnedShoesContext.Provider>
  );
}

export function useOwnedShoes() {
  return useContext(OwnedShoesContext);
}
