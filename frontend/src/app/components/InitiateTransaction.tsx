import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { motion } from "motion/react";
import { User, ChevronRight, Shield, UserPlus, AlertCircle, History, LogOut } from "lucide-react";
import { apiClient } from "../services/api";
import { useUser } from "../context/UserContext";
import { useSessionTimeout } from "../hooks/useSessionTimeout";
import { useOnlineStatus } from "../hooks/useOnlineStatus";
import { toast } from "sonner";

const STATIC_PAYEES = [
  { id: "1", name: "Sarah Johnson", upiId: "sarah@upi" },
  { id: "2", name: "Michael Chen",  upiId: "michael@upi" },
  { id: "3", name: "Priya Sharma",  upiId: "priya@upi" },
  { id: "4", name: "James Wilson",  upiId: "james@upi" },
];

export function InitiateTransaction() {
  const navigate = useNavigate();
  const { user, logout } = useUser();
  const isOnline = useOnlineStatus();
  useSessionTimeout();

  const [amount, setAmount]               = useState("");
  const [selectedPayee, setSelectedPayee] = useState("");
  const [backendUp, setBackendUp]         = useState<boolean | null>(null);
  const [loading, setLoading]             = useState(false);
  const [error, setError]                 = useState<string | null>(null);

  useEffect(() => {
    apiClient.health().then((r) => setBackendUp(r.success));
  }, []);

  const payee   = STATIC_PAYEES.find((p) => p.id === selectedPayee);
  const isValid = !!amount && parseFloat(amount) > 0 && !!selectedPayee;

  const handlePay = async () => {
    if (!isValid) return;
    if (!isOnline) { toast.error("No internet connection"); return; }

    setLoading(true);
    setError(null);

    const userId = user?.userId ?? "demo_user";
    sessionStorage.setItem("pendingTransaction", JSON.stringify({
      userId,
      amount,
      recipientUpi:  payee!.upiId,
      recipientName: payee!.name,
    }));

    if (!backendUp) {
      sessionStorage.setItem("txChallenge", JSON.stringify({
        tx_id:           "demo_" + Date.now(),
        stego_image_b64: "",
        salt_b64:        "",
        pin_positions:   [1, 3, 5],
        amount_rupees:   parseFloat(amount),
        recipient_upi:   payee!.upiId,
        isDemoMode:      true,
      }));
      setLoading(false);
      navigate("/verify-face");
      return;
    }

    setLoading(false);
    navigate("/verify-face");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {!isOnline && (
          <div className="fixed top-0 left-0 right-0 bg-red-500 text-white p-2 text-center text-sm z-50">
            No internet connection. Transactions disabled.
          </div>
        )}

        <div className="mb-4 flex items-center justify-between">
          <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${
            backendUp === null ? "bg-slate-700/50 text-slate-400"
            : backendUp       ? "bg-emerald-500/15 text-emerald-400"
                              : "bg-yellow-500/15 text-yellow-400"
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${
              backendUp === null ? "bg-slate-400" : backendUp ? "bg-emerald-400" : "bg-yellow-400"
            }`} />
            {backendUp === null ? "Checking…" : backendUp ? "Backend Connected" : "Demo Mode"}
          </div>
          <div className="flex gap-2">
            {user && (
              <>
                <button onClick={() => navigate("/history")}
                  className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 transition-colors"
                  title="Transaction History" aria-label="View transaction history">
                  <History className="w-4 h-4" />
                </button>
                <button onClick={logout}
                  className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 transition-colors"
                  title="Logout" aria-label="Logout">
                  <LogOut className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        </div>

        <div className="text-center mb-8">
          <motion.div
            className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 mb-4"
            whileHover={{ scale: 1.05 }}
          >
            <Shield className="w-8 h-8" />
          </motion.div>
          <h1 className="text-3xl mb-1">SecureUPI</h1>
          <p className="text-slate-400 text-sm">Next-gen secure payments</p>
          {user && <p className="text-blue-400 text-xs mt-1">👤 {user.fullName || user.userId}</p>}
        </div>

        <div className="bg-slate-900 rounded-3xl p-6 shadow-2xl border border-slate-800">
          <div className="mb-4">
            <button
              onClick={() => navigate("/register")}
              className="w-full bg-slate-800 border-2 border-dashed border-slate-600 hover:border-blue-500 rounded-xl p-3 transition-all flex items-center justify-center gap-2 text-slate-300 hover:text-white text-sm"
              aria-label="Register a new account"
            >
              <UserPlus className="w-4 h-4" />
              Register New Account
            </button>
          </div>

          <div className="mb-6">
            <label className="text-slate-400 text-sm mb-2 block">Enter Amount</label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-2xl text-slate-400">₹</span>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                min="0.01"
                aria-label="Payment amount in rupees"
                className="w-full bg-slate-800 border border-slate-700 rounded-2xl pl-12 pr-4 py-4 text-2xl text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="mb-6">
            <label className="text-slate-400 text-sm mb-3 block">Select Payee</label>
            <div className="space-y-2">
              {STATIC_PAYEES.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelectedPayee(p.id)}
                  aria-pressed={selectedPayee === p.id}
                  className={`w-full p-4 rounded-xl flex items-center justify-between transition-all ${
                    selectedPayee === p.id
                      ? "bg-blue-500/20 border-2 border-blue-500"
                      : "bg-slate-800 border-2 border-slate-700 hover:border-slate-600"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${selectedPayee === p.id ? "bg-blue-500" : "bg-slate-700"}`}>
                      <User className="w-5 h-5" />
                    </div>
                    <div className="text-left">
                      <div className="text-white">{p.name}</div>
                      <div className="text-slate-400 text-xs">{p.upiId}</div>
                    </div>
                  </div>
                  <ChevronRight className={`w-5 h-5 transition-colors ${selectedPayee === p.id ? "text-blue-400" : "text-slate-600"}`} />
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center gap-2" role="alert" aria-live="polite">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
              <p className="text-red-300 text-sm">{error}</p>
            </div>
          )}

          <motion.button
            onClick={handlePay}
            disabled={!isValid || loading || !isOnline}
            aria-label="Proceed to face verification"
            className={`w-full py-4 rounded-2xl font-semibold flex items-center justify-center gap-2 transition-all ${
              isValid && !loading && isOnline
                ? "bg-gradient-to-r from-blue-500 to-emerald-500 hover:opacity-90 shadow-lg shadow-blue-500/25"
                : "bg-slate-700 text-slate-500 cursor-not-allowed"
            }`}
            whileTap={isValid ? { scale: 0.97 } : {}}
          >
            {loading ? (
              <><span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Processing…</>
            ) : (
              <>Pay Securely <ChevronRight className="w-5 h-5" /></>
            )}
          </motion.button>
        </div>

        <p className="text-center text-slate-600 text-xs mt-6">
          Secured with AES-256 + GAN Steganography
        </p>
      </div>
    </div>
  );
}
