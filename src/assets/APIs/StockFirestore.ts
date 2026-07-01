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

export interface IndexSuggestion {
  symbol: string;
  name: string;
  currency: string;
  exchange: string;
  exchangeFullName: string;
}

export interface VolumeAlert extends IndexSuggestion {
   lastAlertTimestamp: Date | null
}

function volumeAlertsRef(userId: string) {
  return collection(db, "users", userId, "volume_alerts");
}

function requireUser() {
  const user = auth.currentUser;
  if (!user) throw new Error("User not authenticated");
  return user;
}

/**
 * Add IndexSuggestion objects as new volume_alerts documents for the current user.
 * One document per symbol, mirroring the giftcard_alerts structure.
 */
export const addVolumeSymbols = async (symbols: IndexSuggestion[]) => {
  const user = requireUser();

  await Promise.all(
    symbols.map((s) =>
      addDoc(volumeAlertsRef(user.uid), {
        ...s,
        isActive: true,
        lastAlertTimestamp: null,
        createdAt: serverTimestamp(),
      })
    )
  );
};

/**
 * Remove the volume_alerts document matching the given symbol for the current user.
 */
export const removeVolumeSymbol = async (symbolObj: IndexSuggestion) => {
  const user = requireUser();

  const q = query(volumeAlertsRef(user.uid), where("symbol", "==", symbolObj.symbol));
  const snap = await getDocs(q);

  await Promise.all(snap.docs.map((d) => deleteDoc(d.ref)));
};


export const fetchUserVolumeSymbols = async (): Promise<VolumeAlert[]> => {
  const user = auth.currentUser;
  if (!user) return [];

  try {
    const snap = await getDocs(volumeAlertsRef(user.uid));
    const alerts: VolumeAlert[] = snap.docs.map((d) => {
      const data = d.data();
      return {
        symbol: data.symbol,
        name: data.name,
        currency: data.currency,
        exchange: data.exchange,
        exchangeFullName: data.exchangeFullName,
        lastAlertTimestamp: data.lastAlertTimestamp?.toDate?.() ?? null,
      };
    });

    return alerts.sort((a, b) => {
      if (!a.lastAlertTimestamp && !b.lastAlertTimestamp) return 0;
      if (!a.lastAlertTimestamp) return 1;
      if (!b.lastAlertTimestamp) return -1;
      return b.lastAlertTimestamp.getTime() - a.lastAlertTimestamp.getTime();
    });
  } catch (err: any) {
    throw new Error(err.message);
  }
};