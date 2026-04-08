import { createBrowserRouter } from "react-router";
import { InitiateTransaction }  from "./components/InitiateTransaction";
import { FacialRecognition }    from "./components/FacialRecognition";
import { PinVerification }      from "./components/PinVerification";
import { TransactionSuccess }   from "./components/TransactionSuccess";
import { Registration }         from "./components/Registration";
import { TransactionHistory }   from "./components/TransactionHistory";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: InitiateTransaction,
  },
  {
    path: "/register",
    Component: Registration,
  },
  {
    path: "/history",
    Component: TransactionHistory,
  },
  {
    path: "/verify-face",
    Component: FacialRecognition,
  },
  {
    path: "/verify-pin",
    Component: PinVerification,
  },
  {
    path: "/success",
    Component: TransactionSuccess,
  },
]);
