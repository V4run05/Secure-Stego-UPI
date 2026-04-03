import { useState } from "react";
import { useNavigate } from "react-router";
import { motion } from "motion/react";
import { Shield, Lock } from "lucide-react";

export function PinVerification() {
  const navigate = useNavigate();
  const [enteredDigits, setEnteredDigits] = useState<string[]>([]);
  const requiredPositions = [1, 3, 5]; // Positions 1, 3, and 5 (0-indexed: 0, 2, 4)
  const requiredCount = requiredPositions.length;

  const handleDigitClick = (digit: string) => {
    if (enteredDigits.length < requiredCount) {
      const newDigits = [...enteredDigits, digit];
      setEnteredDigits(newDigits);

      // Navigate to success screen when all required digits are entered
      if (newDigits.length === requiredCount) {
        setTimeout(() => {
          navigate("/success");
        }, 500);
      }
    }
  };

  const handleDelete = () => {
    setEnteredDigits((prev) => prev.slice(0, -1));
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 mb-4">
            <Shield className="w-8 h-8" />
          </div>
          <h1 className="text-2xl mb-2">PIN Verification</h1>
          <p className="text-slate-400 text-sm">Layer 2: Dynamic PIN Authentication</p>
        </div>

        {/* Main Card */}
        <div className="bg-slate-900 rounded-3xl p-8 shadow-2xl border border-slate-800">
          {/* Lock Icon */}
          <div className="flex justify-center mb-6">
            <div className="relative">
              <div className="absolute inset-0 bg-blue-500/20 blur-2xl rounded-full" />
              <div className="relative w-20 h-20 rounded-full bg-gradient-to-br from-slate-800 to-slate-900 border-2 border-blue-500/50 flex items-center justify-center">
                <Lock className="w-10 h-10 text-blue-400" />
              </div>
            </div>
          </div>

          {/* Instruction */}
          <div className="text-center mb-8">
            <h2 className="text-xl mb-2">Enter digits at positions</h2>
            <div className="flex items-center justify-center gap-2 text-3xl">
              {requiredPositions.map((pos, index) => (
                <span key={pos}>
                  <span className="text-blue-400">{pos}</span>
                  {index < requiredPositions.length - 1 && (
                    <span className="text-slate-600">, </span>
                  )}
                </span>
              ))}
            </div>
          </div>

          {/* PIN Display */}
          <div className="flex justify-center gap-4 mb-8">
            {Array.from({ length: requiredCount }).map((_, index) => (
              <motion.div
                key={index}
                className={`w-14 h-14 rounded-xl border-2 flex items-center justify-center text-2xl ${
                  enteredDigits[index]
                    ? "border-emerald-500 bg-emerald-500/20 text-emerald-400"
                    : "border-slate-700 bg-slate-800 text-slate-600"
                }`}
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: index * 0.1 }}
              >
                {enteredDigits[index] ? "●" : ""}
              </motion.div>
            ))}
          </div>

          {/* Position Indicators */}
          <div className="mb-6 bg-slate-800 rounded-xl p-4">
            <div className="text-xs text-slate-400 mb-2 text-center">
              Your 6-digit PIN positions:
            </div>
            <div className="flex justify-center gap-2">
              {[1, 2, 3, 4, 5, 6].map((pos) => {
                const isRequired = requiredPositions.includes(pos);
                return (
                  <div
                    key={pos}
                    className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm border-2 ${
                      isRequired
                        ? "border-blue-500 bg-blue-500/20 text-blue-400"
                        : "border-slate-700 bg-slate-900 text-slate-600"
                    }`}
                  >
                    {pos}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Numeric Keypad */}
          <div className="grid grid-cols-3 gap-3">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((digit) => (
              <button
                key={digit}
                onClick={() => handleDigitClick(digit.toString())}
                disabled={enteredDigits.length >= requiredCount}
                className="aspect-square bg-slate-800 hover:bg-slate-700 active:bg-slate-600 border border-slate-700 rounded-2xl text-2xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {digit}
              </button>
            ))}
            <div className="aspect-square" /> {/* Empty space */}
            <button
              onClick={() => handleDigitClick("0")}
              disabled={enteredDigits.length >= requiredCount}
              className="aspect-square bg-slate-800 hover:bg-slate-700 active:bg-slate-600 border border-slate-700 rounded-2xl text-2xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              0
            </button>
            <button
              onClick={handleDelete}
              disabled={enteredDigits.length === 0}
              className="aspect-square bg-slate-800 hover:bg-slate-700 active:bg-slate-600 border border-slate-700 rounded-2xl text-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              ⌫
            </button>
          </div>
        </div>

        {/* Security Notice */}
        <div className="mt-6 text-center text-slate-500 text-xs">
          Dynamic PIN positions change with each transaction
        </div>
      </div>
    </div>
  );
}
