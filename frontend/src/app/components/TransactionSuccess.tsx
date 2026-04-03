import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { motion } from "motion/react";
import { CheckCircle2, Shield, ArrowLeft } from "lucide-react";

interface TransactionData {
  amount: string;
  payee: string;
  upiId: string;
  timestamp: string;
}

export function TransactionSuccess() {
  const navigate = useNavigate();
  const [transaction, setTransaction] = useState<TransactionData | null>(null);

  useEffect(() => {
    const data = localStorage.getItem("transaction");
    if (data) {
      setTransaction(JSON.parse(data));
    }
  }, []);

  const handleNewPayment = () => {
    localStorage.removeItem("transaction");
    navigate("/");
  };

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const transactionId = `TXN${Date.now().toString().slice(-10)}`;

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 mb-4">
            <Shield className="w-8 h-8" />
          </div>
          <h1 className="text-2xl mb-2">SecureUPI</h1>
        </div>

        {/* Main Card */}
        <div className="bg-slate-900 rounded-3xl p-8 shadow-2xl border border-slate-800">
          {/* Success Icon */}
          <motion.div
            className="flex justify-center mb-6"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{
              type: "spring",
              stiffness: 200,
              damping: 15,
              delay: 0.2,
            }}
          >
            <div className="relative">
              {/* Animated glow rings */}
              <motion.div
                className="absolute inset-0 bg-emerald-500/30 blur-3xl rounded-full"
                animate={{
                  scale: [1, 1.2, 1],
                  opacity: [0.5, 0.8, 0.5],
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
              />
              <div className="relative">
                <CheckCircle2 className="w-28 h-28 text-emerald-400 drop-shadow-lg" />
              </div>
            </div>
          </motion.div>

          {/* Success Message */}
          <motion.div
            className="text-center mb-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <h2 className="text-2xl mb-2">Payment Successful</h2>
            <p className="text-slate-400 text-sm">
              Your transaction has been completed securely
            </p>
          </motion.div>

          {/* Amount Display */}
          <motion.div
            className="text-center mb-8 pb-8 border-b border-slate-800"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
          >
            <div className="text-5xl mb-2">
              ₹{transaction?.amount || "0.00"}
            </div>
            <div className="text-emerald-400 text-sm">Transferred Successfully</div>
          </motion.div>

          {/* Transaction Details Card */}
          <motion.div
            className="bg-slate-800 rounded-2xl p-5 mb-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8 }}
          >
            <h3 className="text-sm text-slate-400 mb-4">Transaction Details</h3>
            
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-slate-400 text-sm">To</span>
                <span className="text-white">{transaction?.payee || "N/A"}</span>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-slate-400 text-sm">UPI ID</span>
                <span className="text-white text-sm">{transaction?.upiId || "N/A"}</span>
              </div>
              
              <div className="h-px bg-slate-700" />
              
              <div className="flex justify-between items-center">
                <span className="text-slate-400 text-sm">Transaction ID</span>
                <span className="text-white text-sm font-mono">{transactionId}</span>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-slate-400 text-sm">Date & Time</span>
                <span className="text-white text-sm">
                  {transaction?.timestamp ? formatDate(transaction.timestamp) : "N/A"}
                </span>
              </div>
              
              <div className="h-px bg-slate-700" />
              
              <div className="flex justify-between items-center">
                <span className="text-slate-400 text-sm">Security</span>
                <div className="flex items-center gap-2">
                  <span className="text-emerald-400 text-sm">2-Layer Auth ✓</span>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Verification Badges */}
          <motion.div
            className="grid grid-cols-2 gap-3 mb-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1 }}
          >
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-3 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <div>
                <div className="text-xs text-emerald-400">Face ID</div>
                <div className="text-xs text-slate-400">Verified</div>
              </div>
            </div>
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-3 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <div>
                <div className="text-xs text-emerald-400">PIN Auth</div>
                <div className="text-xs text-slate-400">Verified</div>
              </div>
            </div>
          </motion.div>

          {/* Action Button */}
          <motion.button
            onClick={handleNewPayment}
            className="w-full bg-gradient-to-r from-blue-500 to-emerald-500 text-white py-4 rounded-2xl font-medium text-lg shadow-lg shadow-blue-500/30 hover:shadow-blue-500/50 transition-all flex items-center justify-center gap-2"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.2 }}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <ArrowLeft className="w-5 h-5" />
            New Payment
          </motion.button>
        </div>

        {/* Security Notice */}
        <div className="mt-6 text-center text-slate-500 text-xs">
          Transaction encrypted end-to-end with military-grade security
        </div>
      </div>
    </div>
  );
}
