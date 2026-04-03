import { useState } from "react";
import { useNavigate } from "react-router";
import { User, ChevronRight, Shield } from "lucide-react";

export function InitiateTransaction() {
  const navigate = useNavigate();
  const [amount, setAmount] = useState("");
  const [selectedPayee, setSelectedPayee] = useState("");

  const payees = [
    { id: "1", name: "Sarah Johnson", upiId: "sarah@upi" },
    { id: "2", name: "Michael Chen", upiId: "michael@upi" },
    { id: "3", name: "Priya Sharma", upiId: "priya@upi" },
    { id: "4", name: "James Wilson", upiId: "james@upi" },
  ];

  const handlePaySecurely = () => {
    if (amount && selectedPayee) {
      const payee = payees.find((p) => p.id === selectedPayee);
      localStorage.setItem(
        "transaction",
        JSON.stringify({
          amount,
          payee: payee?.name,
          upiId: payee?.upiId,
          timestamp: new Date().toISOString(),
        })
      );
      navigate("/verify-face");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 mb-4">
            <Shield className="w-8 h-8" />
          </div>
          <h1 className="text-3xl mb-2">SecureUPI</h1>
          <p className="text-slate-400 text-sm">Next-gen secure payments</p>
        </div>

        {/* Main Card */}
        <div className="bg-slate-900 rounded-3xl p-6 shadow-2xl border border-slate-800">
          {/* Amount Input */}
          <div className="mb-6">
            <label className="text-slate-400 text-sm mb-2 block">
              Enter Amount
            </label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-2xl text-slate-400">
                ₹
              </span>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className="w-full bg-slate-800 border border-slate-700 rounded-2xl pl-12 pr-4 py-4 text-2xl text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Payee Selection */}
          <div className="mb-6">
            <label className="text-slate-400 text-sm mb-3 block">
              Select Payee
            </label>
            <div className="space-y-2">
              {payees.map((payee) => (
                <button
                  key={payee.id}
                  onClick={() => setSelectedPayee(payee.id)}
                  className={`w-full p-4 rounded-xl flex items-center justify-between transition-all ${
                    selectedPayee === payee.id
                      ? "bg-blue-500/20 border-2 border-blue-500"
                      : "bg-slate-800 border-2 border-slate-700 hover:border-slate-600"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center ${
                        selectedPayee === payee.id
                          ? "bg-blue-500"
                          : "bg-slate-700"
                      }`}
                    >
                      <User className="w-5 h-5" />
                    </div>
                    <div className="text-left">
                      <div className="text-white">{payee.name}</div>
                      <div className="text-slate-400 text-xs">
                        {payee.upiId}
                      </div>
                    </div>
                  </div>
                  <ChevronRight
                    className={`w-5 h-5 ${
                      selectedPayee === payee.id
                        ? "text-blue-500"
                        : "text-slate-600"
                    }`}
                  />
                </button>
              ))}
            </div>
          </div>

          {/* Pay Button */}
          <button
            onClick={handlePaySecurely}
            disabled={!amount || !selectedPayee}
            className="w-full bg-gradient-to-r from-blue-500 to-emerald-500 text-white py-4 rounded-2xl font-medium text-lg shadow-lg shadow-blue-500/30 hover:shadow-blue-500/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
          >
            Pay Securely
          </button>
        </div>

        {/* Security Notice */}
        <div className="mt-6 text-center text-slate-500 text-xs">
          Protected by multi-layer biometric verification
        </div>
      </div>
    </div>
  );
}
