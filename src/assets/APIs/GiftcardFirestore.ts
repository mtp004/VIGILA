import { db, auth } from "../../firebase";
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
export type AutoStatus = "pending" | "collecting" | "insufficient_data" | "active" | "unmapped";

export const PATIENCE_OPTIONS: { value: GiftcardPatience; label: string; days: number }[] = [
  { value: "manual", label: "Manual", days: 0 },
  { value: "1m", label: "1 month", days: 30 },
  { value: "3m", label: "3 months", days: 90 },
  { value: "6m", label: "6 months", days: 180 },
];

// Must match HISTORY_MULTIPLIER in gcf/giftcard_alert_backend/auto_trigger.py
export const AUTO_TRIGGER_HISTORY_MULTIPLIER = 2;

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
  // Auto trigger, written by the scraper's recompute; minDiscountPercent stays the manual trigger
  computedTrigger?: number | null;
  computedAt?: Timestamp | null;
  episodes?: number | null;
  historyDays?: number | null;
  autoStatus?: AutoStatus;
}

const PENDING_AUTO_TRIGGER = { autoStatus: "pending" as AutoStatus, computedTrigger: null };

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

// resetAutoTrigger: the brand, range or platforms changed, so any computed trigger is stale
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
  const value = snap.data()?.giftcardPatience;
  return PATIENCE_OPTIONS.some((o) => o.value === value) ? value : "manual";
};

// Switching to an auto option marks every alert pending so the next scrape run recomputes it
export const saveGiftcardPatience = async (patience: GiftcardPatience): Promise<void> => {
  const user = requireUser();
  const batch = writeBatch(db);
  batch.set(doc(db, "users", user.uid), { giftcardPatience: patience }, { merge: true });
  if (patience !== "manual") {
    const snap = await getDocs(alertsRef(user.uid));
    snap.docs.forEach((d) => batch.update(d.ref, PENDING_AUTO_TRIGGER));
  }
  await batch.commit();
};
