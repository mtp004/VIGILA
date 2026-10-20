import { auth } from "../../firebase";
import { db } from "../../firestore";
import {
  collection,
  doc,
  addDoc,
  getDocs,
  updateDoc,
  deleteDoc,
  getDoc,
  writeBatch,
  serverTimestamp,
  Timestamp,
} from "firebase/firestore";

export type GiftcardPatience = "manual" | "1m" | "3m" | "6m";

// historyDays: days needed before optimizing (2 x patience, see auto_trigger.py)
export const PATIENCE_OPTIONS: { value: GiftcardPatience; label: string; historyDays: number }[] = [
  { value: "manual", label: "Manual", historyDays: 0 },
  { value: "1m", label: "1 month", historyDays: 60 },
  { value: "3m", label: "3 months", historyDays: 180 },
  { value: "6m", label: "6 months", historyDays: 360 },
];

export interface GiftCardAlert {
  id: string;
  brand: string;
  minCardValue: number;
  maxCardValue: number;
  minDiscountPercent: number;
  isActive: boolean;
  lastCheckedAt: Timestamp | null;
  createdAt: Timestamp;
  urls: { gcx: string; cardcash: string; carddepot: string };
  platforms: {
    gcx: { active: boolean; highest_discount?: number };
    cardcash: { active: boolean; highest_discount?: number };
    carddepot: { active: boolean; highest_discount?: number };
  };
  satisfied_by: string[];
  // Written by the scraper's recompute; minDiscountPercent stays the manual trigger
  computedTrigger?: number | null;
  computedAt?: Timestamp | null;
  episodes?: number | null;
  historyDays?: number | null;
  autoStatus?: "pending" | "collecting" | "insufficient_data" | "active" | "unmapped";
}

export const PENDING_AUTO_TRIGGER = { autoStatus: "pending", computedTrigger: null } as const;

export interface AlertFormData {
  brand: string;
  minCardValue: number;
  maxCardValue: number;
  minDiscountPercent: number;
  platforms: { gcx: boolean; cardcash: boolean; carddepot: boolean };
  urls: { gcx: string; cardcash: string; carddepot: string };
}

function alertsRef(userId: string) {
  return collection(db, "users", userId, "giftcard_alerts");
}

function alertDoc(userId: string, alertId: string) {
  return doc(db, "users", userId, "giftcard_alerts", alertId);
}

function requireUser() {
  const user = auth.currentUser;
  if (!user) throw new Error("User not authenticated");
  return user;
}

export const createAlert = async (data: AlertFormData): Promise<string> => {
  const user = requireUser();
  const docRef = await addDoc(alertsRef(user.uid), {
    ...data,
    platforms: {
      gcx: { active: data.platforms.gcx },
      cardcash: { active: data.platforms.cardcash },
      carddepot: { active: data.platforms.carddepot },
    },
    isActive: true,
    satisfied_by: [],
    ...PENDING_AUTO_TRIGGER,
    lastCheckedAt: null,
    createdAt: serverTimestamp(),
  });
  return docRef.id;
};

export const fetchAlerts = async (): Promise<GiftCardAlert[]> => {
  const user = requireUser();
  const snap = await getDocs(alertsRef(user.uid));
  return snap.docs.map((d) => ({ id: d.id, ...d.data() } as GiftCardAlert));
};

export const updateAlert = async (
  alertId: string,
  data: Partial<AlertFormData>,
  resetAutoTrigger = false
): Promise<void> => {
  const user = requireUser();
  const payload: any = { ...data };
  if (data.platforms) {
    delete payload.platforms;
    payload["platforms.gcx.active"] = data.platforms.gcx;
    payload["platforms.cardcash.active"] = data.platforms.cardcash;
    payload["platforms.carddepot.active"] = data.platforms.carddepot;
  }
  payload.satisfied_by = [];
  payload.lastCheckedAt = null;
  if (resetAutoTrigger) Object.assign(payload, PENDING_AUTO_TRIGGER);
  await updateDoc(alertDoc(user.uid, alertId), payload);
};

export const deleteAlert = async (alertId: string): Promise<void> => {
  const user = requireUser();
  await deleteDoc(alertDoc(user.uid, alertId));
};

export const toggleAlert = async (
  alertId: string,
  isActive: boolean
): Promise<void> => {
  const user = requireUser();
  await updateDoc(alertDoc(user.uid, alertId), { isActive });
};

export const fetchGiftcardPatience = async (): Promise<GiftcardPatience> => {
  const user = requireUser();
  const snap = await getDoc(doc(db, "users", user.uid));
  return snap.data()?.giftcardPatience ?? "manual";
};

// Marks the given alerts pending so the next scrape run recomputes them. Takes the ids
// the caller already has to save a read; an alert missing from them is caught by the daily full recompute.
export const saveGiftcardPatience = async (patience: GiftcardPatience, alertIds: string[]): Promise<void> => {
  const user = requireUser();
  const commit = (ids: string[]) => {
    const batch = writeBatch(db);
    batch.set(doc(db, "users", user.uid), { giftcardPatience: patience }, { merge: true });
    if (patience !== "manual") {
      ids.forEach((id) => batch.update(alertDoc(user.uid, id), PENDING_AUTO_TRIGGER));
    }
    return batch.commit();
  };
  try {
    await commit(alertIds);
  } catch (err) {
    // An alert deleted elsewhere fails the whole batch; retry once with the current ids
    if ((err as { code?: string }).code !== "not-found") throw err;
    const snap = await getDocs(alertsRef(user.uid));
    await commit(snap.docs.map((d) => d.id));
  }
};
