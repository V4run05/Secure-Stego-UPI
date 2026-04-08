import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { motion } from "motion/react";
import { Shield, AlertCircle } from "lucide-react";
import { WebcamCapture } from "./WebcamCapture";
import { apiClient } from "../services/api";
import { toast } from "sonner";

export function FacialRecognition() {
  const navigate = useNavigate();
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [isVerifying, setIsVerifying]     = useState(false);
  const [error, setError]                 = useState<string | null>(null);
  const [attemptsLeft, setAttemptsLeft]   = useState<number | null>(null);

  useEffect(() => {
    const pending = sessionStorage.getItem("pendingTransaction");
    if (!pending) {
      toast.error("No transaction found. Start a new payment.");
      navigate("/");
    }
  }, [navigate]);

  const handleCapture = async (imageBase64: string) => {
    setCapturedImage(imageBase64);
    setIsVerifying(true);
    setError(null);

    const pending = sessionStorage.getItem("pendingTransaction");
    if (!pending) { navigate("/"); return; }

    const txData = JSON.parse(pending) as {
      userId: string;
      amount: string;
      recipientUpi: string;
    };

    const result = await apiClient.initiateTransaction({
      user_id:        txData.userId,
      face_image_b64: imageBase64,
      amount_rupees:  parseFloat(txData.amount),
      recipient_upi:  txData.recipientUpi,
    });

    if (result.success) {
      sessionStorage.setItem("txChallenge", JSON.stringify(result.data));
      toast.success("Face verified!");
      setTimeout(() => navigate("/verify-pin"), 600);
    } else {
      const details = (result as { success: false; error: string; details?: { attempts_remaining?: number } }).details;
      setAttemptsLeft(details?.attempts_remaining ?? null);
      setError(result.error);
      setIsVerifying(false);
      setCapturedImage(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 mb-4">
            <Shield className="w-8 h-8" />
          </div>
          <h1 className="text-2xl mb-2">Biometric Verification</h1>
          <p className="text-slate-400 text-sm">Layer 1: Face Authentication</p>
        </div>

        <div className="bg-slate-900 rounded-3xl p-6 shadow-2xl border border-slate-800">
          {error && (
            <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 flex items-start gap-2" role="alert" aria-live="assertive">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-red-300 text-sm font-medium">Verification Failed</p>
                <p className="text-red-200 text-xs">{error}</p>
                {attemptsLeft !== null && (
                  <p className="text-yellow-400 text-xs mt-1">Attempts remaining: {attemptsLeft}</p>
                )}
              </div>
            </div>
          )}

          {isVerifying && capturedImage ? (
            <div className="flex flex-col items-center gap-4 py-8">
              <img
                src={`data:image/jpeg;base64,${capturedImage}`}
                alt="Captured face"
                className="w-48 h-48 rounded-full object-cover border-4 border-blue-500/50"
              />
              <motion.div
                className="flex items-center gap-3"
                animate={{ opacity: [1, 0.5, 1] }}
                transition={{ duration: 1.2, repeat: Infinity }}
              >
                <span className="w-5 h-5 border-2 border-blue-400/40 border-t-blue-400 rounded-full animate-spin" />
                <span className="text-blue-300">Verifying identity…</span>
              </motion.div>
              <p className="text-slate-500 text-xs">Comparing face embedding via ArcFace</p>
            </div>
          ) : (
            <WebcamCapture onCapture={handleCapture} showFaceGuide />
          )}

          <div className="mt-6 grid grid-cols-3 gap-3">
            {[
              { label: "Liveness",  desc: "Anti-spoof check" },
              { label: "Depth",     desc: "3D face analysis" },
              { label: "Texture",   desc: "Skin texture scan" },
            ].map(({ label, desc }) => (
              <div key={label} className="bg-slate-800 rounded-xl p-3 text-center">
                <div className="text-xs text-slate-400 mb-1">{label}</div>
                <div className="text-slate-500 text-xs">{desc}</div>
              </div>
            ))}
          </div>
        </div>

        <p className="mt-6 text-center text-slate-500 text-xs">
          Biometric data is processed locally and never stored as raw images
        </p>
      </div>
    </div>
  );
}
