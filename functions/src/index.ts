import {setGlobalOptions} from "firebase-functions";
import {beforeUserCreated, HttpsError} from "firebase-functions/v2/identity";
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
