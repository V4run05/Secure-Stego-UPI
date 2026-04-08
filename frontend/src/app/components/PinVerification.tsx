import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { motion } from "motion/react";
import { Shield, Lock, AlertCircle, Clock } from "lucide-react";
import { apiClient } from "../services/api";
import { toast } from "sonner";

interface TxChallenge {
  tx_id:           string;
  stego_image_b64: string;
  salt_b64:        string;
  pin_positions:   number[];
  amount_rupees:   number;
  recipient_upi:   string;
  isDemoMode?:     boolean;
}

export function PinVerification() {
  const navigate = useNavigate();
  const [challenge, setChallenge]     = useState<TxChallenge | null>(null);
  const [enteredDigits, setEnteredDigits] = useState<Record<number, string>>({});
  const [submitting, setSubmitting]   = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const [attemptsLeft, setAttemptsLeft] = useState<number | null>(null);
  const [timeLeft, setTimeLeft]       = useState(300);

  useEffect(() => {
    const raw = sessionStorage.getItem("txChallenge");
    if (!raw) {
      toast.error("No transaction challenge found. Please start over.");
      navigate("/");
      return;
    }
    setChallenge(JSON.parse(raw) as TxChallenge);
  }, [navigate]);

  useEffect(() => {
    if (!challenge) return;
    const interval = setInterval(() => {
      setTimeLeft((t) => {
        if (t <= 1) {
          clearInterval(interval);
          toast.error("Session expired. Please start over.");
          sessionStorage.removeItem("txChallenge");
          navigate("/");
          return 0;
        }
        return t - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [challenge, navigate]);

  useEffect(() => {
    return () => sessionStorage.removeItem("txChallenge");
  }, []);

  const positions: number[] = challenge?.pin_positions ?? [];
  const filled = positions.filter((p) => enteredDigits[p] !== undefined);
  const isComplete = filled.length === positions.length;

  const handleDigit = (digit: string) => {
    const nextPos = positions.find((p) => enteredDigits[p] === undefined);
    if (nextPos === undefined) return;
    const updated = { ...enteredDigits, [nextPos]: digit };
    setEnteredDigits(updated);
    if (Object.keys(updated).length === positions.length) {
      handleSubmit(updated);
    }
  };

  const handleDelete = () => {
    const lastFilled = [...positions].reverse().find((p) => enteredDigits[p] !== undefined);
    if (lastFilled !== undefined) {
      const updated = { ...enteredDigits };
      delete updated[lastFilled];
      setEnteredDigits(updated);
    }
  };

  const handleSubmit = async (digits: Record<number, string>) => {
    if (!challenge) return;
    setSubmitting(true);
    setError(null);

    if (challenge.isDemoMode) {
      toast.success("Transaction authorized! (Demo mode)");
      sessionStorage.setItem("receipt", JSON.stringify({
        tx_id:         challenge.tx_id,
        amount_rupees: challenge.amount_rupees,
        recipient_upi: challenge.recipient_upi,
        status:        "authorized",
        timestamp:     Date.now() / 1000,
      }));
      setTimeout(() => navigate("/success"), 500);
      setSubmitting(false);
      return;
    }

    const pinDigits: Record<string, string> = {};
    for (const [pos, digit] of Object.entries(digits)) {
      pinDigits[String(pos)] = digit;
    }

    const result = await apiClient.verifyTransaction({
      tx_id:      challenge.tx_id,
      pin_digits: pinDigits,
    });

    if (result.success && result.data.authorized) {
      sessionStorage.setItem("receipt", JSON.stringify(result.data.receipt));
      toast.success("Transaction authorized!");
      navigate("/success");
    } else {
      const data = result.success ? result.data : { reason: result.error, attempts_remaining: null };
      setError(data.reason ?? "Verification failed");
      setAttemptsLeft(data.attempts_remaining ?? null);
      setEnteredDigits({});
      setSubmitting(false);
      if (data.attempts_remaining === 0) {
        toast.error("Account locked after too many failures.");
        setTimeout(() => navigate("/"), 2000);
      }
    }
  };

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 mb-4">
            <Shield className="w-8 h-8" />
          </div>
          <h1 className="text-2xl mb-2">PIN Verification</h1>
          <p className="text-slate-400 text-sm">Layer 2: Dynamic PIN Authentication</p>
        </div>

        <div className="bg-slate-900 rounded-3xl p-8 shadow-2xl border border-slate-800">
          <div className="flex justify-center mb-6">
            <div className="relative">
              <div className="absolute inset-0 bg-blue-500/20 blur-2xl rounded-full" />
              <div className="relative w-20 h-20 rounded-full bg-gradient-to-br from-slate-800 to-slate-900 border-2 border-blue-500/50 flex items-center justify-center">
                <Lock className="w-10 h-10 text-blue-400" />
              </div>
            </div>
          </div>

          {challenge && (
            <div className="text-center mb-2 text-slate-400 text-xs">
              ₹{challenge.amount_rupees?.toFixed(2)} → {challenge.recipient_upi}
            </div>
          )}

          <div className="flex items-center justify-center gap-1 mb-4">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span className={`text-xs ${timeLeft < 60 ? "text-red-400" : "text-slate-500"}`}>
              Session expires in {formatTime(timeLeft)}
            </span>
          </div>

          {challenge?.isDemoMode && (
            <div className="mb-4 p-2 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-center">
              <p className="text-yellow-400 text-xs">Demo Mode — any PIN digits will be accepted</p>
            </div>
          )}

          <div className="text-center mb-6">
            <h2 className="text-lg mb-2">Enter digits at positions</h2>
            <div className="flex items-center justify-center gap-2 text-2xl">
              {positions.map((pos, i) => (
                <span key={pos}>
                  <span className="text-blue-400">{pos}</span>
                  {i < positions.length - 1 && <span className="text-slate-600">, </span>}
                </span>
              ))}
            </div>
          </div>

          <div className="flex justify-center gap-4 mb-6">
            {positions.map((pos, index) => (
              <motion.div
                key={pos}
                className={`w-14 h-14 rounded-xl border-2 flex items-center justify-center text-2xl ${
                  enteredDigits[pos] !== undefined
                    ? "border-emerald-500 bg-emerald-500/20 text-emerald-400"
                    : "border-slate-700 bg-slate-800 text-slate-600"
                }`}
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: index * 0.08 }}
                aria-label={`Digit slot ${index + 1}`}
              >
                {enteredDigits[pos] !== undefined ? "●" : ""}
              </motion.div>
            ))}
          </div>

          <div className="mb-6 bg-slate-800 rounded-xl p-4">
            <div className="text-xs text-slate-400 mb-2 text-center">Your PIN positions:</div>
            <div className="flex justify-center gap-2">
              {[1, 2, 3, 4, 5, 6].map((pos) => {
                const isRequired = positions.includes(pos);
                return (
                  <div key={pos}
                    className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm border-2 ${
                      isRequired
                        ? "border-blue-500 bg-blue-500/20 text-blue-400"
                        : "border-slate-700 bg-slate-900 text-slate-600"
                    }`}>
                    {pos}
                  </div>
                );
              })}
            </div>
          </div>

          {error && (
            <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 flex items-start gap-2" role="alert" aria-live="assertive">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-red-300 text-sm">{error}</p>
                {attemptsLeft !== null && (
                  <p className="text-yellow-400 text-xs mt-1">Attempts remaining: {attemptsLeft}</p>
                )}
              </div>
            </div>
          )}

          <div className="grid grid-cols-3 gap-3">
            {[1,2,3,4,5,6,7,8,9].map((digit) => (
              <button key={digit} onClick={() => handleDigit(digit.toString())}
                disabled={isComplete || submitting}
                aria-label={`Digit ${digit}`}
                className="aspect-square bg-slate-800 hover:bg-slate-700 active:bg-slate-600 border border-slate-700 rounded-2xl text-2xl transition-all disabled:opacity-50 disabled:cursor-not-allowed">
                {digit}
              </button>
            ))}
            <div className="aspect-square" />
            <button onClick={() => handleDigit("0")}
              disabled={isComplete || submitting}
              aria-label="Digit 0"
              className="aspect-square bg-slate-800 hover:bg-slate-700 active:bg-slate-600 border border-slate-700 rounded-2xl text-2xl transition-all disabled:opacity-50 disabled:cursor-not-allowed">
              0
            </button>
            <button onClick={handleDelete}
              disabled={Object.keys(enteredDigits).length === 0 || submitting}
              aria-label="Delete last digit"
              className="aspect-square bg-slate-800 hover:bg-slate-700 active:bg-slate-600 border border-slate-700 rounded-2xl text-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed">
              ⌫
            </button>
          </div>

          {submitting && (
            <div className="mt-4 text-center text-slate-400 text-sm flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-blue-400/40 border-t-blue-400 rounded-full animate-spin" />
              Verifying PIN…
            </div>
          )}
        </div>

        <p className="mt-6 text-center text-slate-500 text-xs">
          Dynamic PIN positions change with each transaction
        </p>
      </div>
    </div>
  );
}
