import {setGlobalOptions} from "firebase-functions";
import {beforeUserCreated, HttpsError} from "firebase-functions/v2/identity";
import {onDocumentDeleted} from "firebase-functions/v2/firestore";
import {initializeApp} from "firebase-admin/app";
import {getFirestore} from "firebase-admin/firestore";

setGlobalOptions({maxInstances: 10});

initializeApp();

export const beforeCreate = beforeUserCreated(async (event) => {
  const email = event.data?.email;
  if (!email) {
    throw new HttpsError(
      "invalid-argument",
      "An email address is required to register.",
    );
  }

  const db = getFirestore();

  const config = await db.collection("app_config").doc("signup").get();
  const mode = config.data()?.mode;
  const emails: string[] = config.data()?.emails ?? [];

  if (mode === "all") {
    return;
  }

  if (mode === "selected") {
    if (!emails.includes(email)) {
      throw new HttpsError(
        "permission-denied",
        "This email is not authorized.",
      );
    }
  }
});

/**
 * Fires whenever a user's volume_profile_alerts doc is deleted. If no
 * other user still has an alert for that symbol, clears its entry in
 * the shared volume_profile_cache (the month-base histogram and its
 * alert log) -- nothing would ever read or refresh it otherwise.
 *
 * Runs with the Admin SDK, so it needs no client-facing Firestore rule
 * changes: users never gain read access to each other's alert docs or
 * delete access to volume_profile_cache directly.
 */
export const cleanupOrphanedVolumeProfileCache = onDocumentDeleted(
  "users/{uid}/volume_profile_alerts/{alertId}",
  async (event) => {
    const symbol = event.data?.data()?.symbol;
    if (!symbol) return;

    const db = getFirestore();

    const remaining = await db
      .collectionGroup("volume_profile_alerts")
      .where("symbol", "==", symbol)
      .limit(1)
      .get();

    if (!remaining.empty) return;

    const cacheDocRef = db.collection("volume_profile_cache").doc(symbol);

    const [monthsSnap, logSnap] = await Promise.all([
      cacheDocRef.collection("months").get(),
      cacheDocRef.collection("alert_log").get(),
    ]);

    const batch = db.batch();
    monthsSnap.docs.forEach((d) => batch.delete(d.ref));
    logSnap.docs.forEach((d) => batch.delete(d.ref));
    batch.delete(cacheDocRef);

    await batch.commit();
  }
);