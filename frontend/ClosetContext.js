import React, { createContext, useContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'ownedShoes';

const ClosetContext = createContext(null);

export function OwnedShoesProvider({ children }) {
  const [ownedMap, setOwnedMap] = useState({});

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((raw) => {
        if (raw) setOwnedMap(JSON.parse(raw));
      })
      .catch((err) => {
        console.error('Failed to load owned shoes:', err);
        setOwnedMap({});
      });
  }, []);

  function toggleOwned(shoe) {
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

  return (
    <ClosetContext.Provider value={{ ownedMap, toggleOwned, isOwned }}>
      {children}
    </ClosetContext.Provider>
  );
}

export function useOwnedShoes() {
  return useContext(ClosetContext);
}
