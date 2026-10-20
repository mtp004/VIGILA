import { getApp } from "firebase/app";
import { getFirestore } from "firebase/firestore";
import "./firebase"; // initializes the app

// Kept out of firebase.ts so the login page doesn't download Firestore
export const db = getFirestore(getApp());
