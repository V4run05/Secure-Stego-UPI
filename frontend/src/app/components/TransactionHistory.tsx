import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { motion } from "motion/react";
import { ArrowLeft, Clock, CheckCircle2, XCircle, AlertCircle, List } from "lucide-react";
import { apiClient, TransactionRecord } from "../services/api";
import { useUser } from "../context/UserContext";

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { icon: JSX.Element; color: string }> = {
    AUTHORIZED:   { icon: <CheckCircle2 className="w-4 h-4" />, color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30" },
    PENDING_PIN:  { icon: <Clock className="w-4 h-4" />,        color: "text-yellow-400 bg-yellow-500/10 border-yellow-500/30" },
    REJECTED:     { icon: <XCircle className="w-4 h-4" />,      color: "text-red-400 bg-red-500/10 border-red-500/30" },
    EXPIRED:      { icon: <AlertCircle className="w-4 h-4" />,  color: "text-slate-400 bg-slate-700/50 border-slate-600" },
  };
  const cfg = map[status] ?? { icon: null, color: "text-slate-400 bg-slate-800 border-slate-700" };
  return (
    <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border ${cfg.color}`}>
      {cfg.icon} {status.replace("_", " ")}
    </span>
  );
}

export function TransactionHistory() {
  const navigate = useNavigate();
  const { user } = useUser();
  const [txs, setTxs] = useState<TransactionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user?.userId) {
      navigate("/");
      return;
    }
    (async () => {
      const result = await apiClient.listTransactions(user.userId);
      if (result.success) {
        setTxs(result.data.transactions);
      } else {
        setError(result.error);
      }
      setLoading(false);
    })();
  }, [user, navigate]);

  return (
    <div className="min-h-screen bg-slate-950 text-white p-4">
      <div className="max-w-md mx-auto">
        <div className="flex items-center gap-4 mb-6">
          <button onClick={() => navigate("/")} className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-semibold">Transaction History</h1>
            <p className="text-slate-400 text-sm">{user?.userId}</p>
          </div>
        </div>

        {loading && (
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-slate-900 rounded-2xl p-4 border border-slate-800 animate-pulse">
                <div className="flex justify-between mb-2">
                  <div className="h-5 bg-slate-700 rounded w-2/5" />
                  <div className="h-5 bg-slate-700 rounded w-1/4" />
                </div>
                <div className="h-3 bg-slate-800 rounded w-1/3" />
              </div>
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-300 text-sm flex items-center gap-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            {error}
          </div>
        )}

        {!loading && !error && txs.length === 0 && (
          <div className="text-center py-16">
            <List className="w-12 h-12 mx-auto mb-3 text-slate-600" />
            <p className="text-slate-400">No transactions yet</p>
            <p className="text-slate-600 text-sm mt-1">Initiate your first payment to see history</p>
          </div>
        )}

        {!loading && txs.map((tx, i) => (
          <motion.div
            key={tx.tx_id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="bg-slate-900 rounded-2xl p-4 mb-3 border border-slate-800 hover:border-slate-700 transition-colors"
          >
            <div className="flex justify-between items-start mb-2">
              <div>
                <p className="font-medium text-lg">₹{tx.amount_rupees.toFixed(2)}</p>
                <p className="text-slate-400 text-sm">to {tx.recipient_upi}</p>
              </div>
              <StatusBadge status={tx.status} />
            </div>
            <p className="text-slate-500 text-xs">
              {new Date(tx.timestamp * 1000).toLocaleString()}
            </p>
            <p className="text-slate-700 text-xs font-mono mt-1 truncate">{tx.tx_id}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
