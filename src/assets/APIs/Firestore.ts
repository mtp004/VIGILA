// src/firebase/firestore.ts
import { db, auth } from "../../firebase";
import { doc, getDoc, setDoc, updateDoc, arrayUnion, arrayRemove } from "firebase/firestore";

export interface IndexSuggestion {
  symbol: string;
  name: string;
  currency: string;
  exchange: string;
  exchangeFullName: string;
}

/**
 * Add IndexSuggestion objects to the current user's Volume indicators.
 */
export const addVolumeSymbols = async (symbols: IndexSuggestion[]) => {
  const user = auth.currentUser;
  if (!user) throw new Error("User not authenticated");

  const userDocRef = doc(db, "users", user.uid);

  // Ensure the document exists
  const snap = await getDoc(userDocRef);
  if (!snap.exists()) {
    await setDoc(userDocRef, { indicators: { Volume: [] } });
  }

  // Append objects without overwriting
  await updateDoc(userDocRef, {
    "indicators.Volume": arrayUnion(...symbols),
  });
};

/**
 * Remove an IndexSuggestion object from the current user's Volume indicators.
 */
export const removeVolumeSymbol = async (symbolObj: IndexSuggestion) => {
  const user = auth.currentUser;
  if (!user) throw new Error("User not authenticated");

  const userDocRef = doc(db, "users", user.uid);

  await updateDoc(userDocRef, {
    "indicators.Volume": arrayRemove(symbolObj),
  });
};

/**
 * Fetch the current user's Volume indicators as IndexSuggestion objects.
 */
export const fetchUserVolumeSymbols = async (): Promise<IndexSuggestion[]> => {
  const user = auth.currentUser;
  if (!user) return [];

  try {
    const userDocRef = doc(db, "users", user.uid);
    const snap = await getDoc(userDocRef);
    if (snap.exists()) {
      const data = snap.data();
      return data?.indicators?.Volume || [];
    } else {
      return [];
    }
  } catch (err: any) {
    throw new Error(err.message);
  }
};
