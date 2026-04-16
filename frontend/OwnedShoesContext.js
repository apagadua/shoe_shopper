import React, { createContext, useContext, useEffect, useState } from 'react';
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

  function toggleOwned(shoe) {
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
  }

  function isOwned(id) {
    return Boolean(ownedMap[id]);
  }

  const ownedShoes = Object.values(ownedMap);

  return (
    <OwnedShoesContext.Provider value={{ ownedMap, ownedShoes, toggleOwned, isOwned }}>
      {children}
    </OwnedShoesContext.Provider>
  );
}

export function useOwnedShoes() {
  return useContext(OwnedShoesContext);
}
