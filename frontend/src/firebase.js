import { initializeApp } from "firebase/app";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: "AIzaSyBIIS9q1DlB1_O4b-ZQxYnUhhCoiuD-8TQ",
  authDomain: "trading-live-logs.firebaseapp.com",
  projectId: "trading-live-logs",
  storageBucket: "trading-live-logs.firebasestorage.app",
  messagingSenderId: "597068304142",
  appId: "1:597068304142:web:1e2bdaebde86fd506ed15f",
  measurementId: "G-4DSBJCER1J"
};

const app = initializeApp(firebaseConfig);
export const db = getFirestore(app);
