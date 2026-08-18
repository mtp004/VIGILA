import { db, auth } from "../../firebase";
import {
  collection,
  query,
  where,
  getDocs,
  addDoc,
  deleteDoc,
  serverTimestamp,
} from "firebase/firestore";
import { type IndexSuggestion } from "./StockFirestore";

export interface VolumeProfileAlert extends IndexSuggestion {}

function volumeProfileAlertsRef(userId: string) {
  return collection(db, "users", userId, "volume_profile_alerts");
}

function requireUser() {
  const user = auth.currentUser;
  if (!user) throw new Error("User not authenticated");
  return user;
}

/**
 * Add IndexSuggestion objects as new volume_profile_alerts documents for
 * the current user. One document per symbol, mirroring volume_alerts.
 */
export const addVolumeProfileSymbols = async (symbols: IndexSuggestion[]) => {
  const user = requireUser();

  await Promise.all(
    symbols.map((s) =>
      addDoc(volumeProfileAlertsRef(user.uid), {
        ...s,
        createdAt: serverTimestamp(),
      })
    )
  );
};

/**
 * Remove the volume_profile_alerts document matching the given symbol
 * for the current user. If that was the last subscriber for the symbol,
 * the cleanupOrphanedVolumeProfileCache Cloud Function (triggered by
 * this delete) clears its entry in volume_profile_cache server-side.
 */
export const removeVolumeProfileSymbol = async (symbolObj: IndexSuggestion) => {
  const user = requireUser();

  const q = query(volumeProfileAlertsRef(user.uid), where("symbol", "==", symbolObj.symbol));
  const snap = await getDocs(q);

  await Promise.all(snap.docs.map((d) => deleteDoc(d.ref)));
};

export const fetchUserVolumeProfileSymbols = async (): Promise<VolumeProfileAlert[]> => {
  const user = auth.currentUser;
  if (!user) return [];

  try {
    const snap = await getDocs(volumeProfileAlertsRef(user.uid));
    const alerts: VolumeProfileAlert[] = snap.docs.map((d) => {
      const data = d.data();
      return {
        symbol: data.symbol,
        name: data.name,
        currency: data.currency,
        exchange: data.exchange,
        exchangeFullName: data.exchangeFullName,
      };
    });

    return alerts.sort((a, b) => a.symbol.localeCompare(b.symbol));
  } catch (err: any) {
    throw new Error(err.message);
  }
};