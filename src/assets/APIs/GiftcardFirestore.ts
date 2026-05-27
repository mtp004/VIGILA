import { db, auth } from "../../firebase";
import {
  collection,
  doc,
  addDoc,
  getDocs,
  updateDoc,
  deleteDoc,
  serverTimestamp,
  Timestamp,
} from "firebase/firestore";
import { type WithFieldValue } from "firebase/firestore";

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
  platforms: { gcx: boolean; cardcash: boolean; carddepot: boolean };
  satisfied_by: string[];
}

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
    isActive: true,
    satisfied_by: [],
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
  data: Partial<AlertFormData>
): Promise<void> => {
  const user = requireUser();
  await updateDoc(
    alertDoc(user.uid, alertId), 
    data as WithFieldValue<Partial<AlertFormData>>
  );
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