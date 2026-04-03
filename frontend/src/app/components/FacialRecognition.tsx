import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { motion } from "motion/react";
import { Shield, ScanFace } from "lucide-react";

export function FacialRecognition() {
  const navigate = useNavigate();
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    // Start scanning animation after component mounts
    const startTimer = setTimeout(() => {
      setScanning(true);
    }, 500);

    return () => clearTimeout(startTimer);
  }, []);

  useEffect(() => {
    if (scanning) {
      // Simulate scanning progress
      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 100) {
            clearInterval(interval);
            // Navigate to PIN verification after successful scan
            setTimeout(() => {
              navigate("/verify-pin");
            }, 800);
            return 100;
          }
          return prev + 2;
        });
      }, 40);

      return () => clearInterval(interval);
    }
  }, [scanning, navigate]);

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 mb-4">
            <Shield className="w-8 h-8" />
          </div>
          <h1 className="text-2xl mb-2">Biometric Verification</h1>
          <p className="text-slate-400 text-sm">Layer 1: Face Authentication</p>
        </div>

        {/* Main Card */}
        <div className="bg-slate-900 rounded-3xl p-8 shadow-2xl border border-slate-800">
          {/* Camera Viewfinder */}
          <div className="relative flex items-center justify-center mb-8">
            {/* Outer glow ring */}
            <motion.div
              className="absolute inset-0 flex items-center justify-center"
              animate={{
                scale: scanning ? [1, 1.1, 1] : 1,
                opacity: scanning ? [0.5, 0.8, 0.5] : 0.3,
              }}
              transition={{
                duration: 2,
                repeat: scanning ? Infinity : 0,
                ease: "easeInOut",
              }}
            >
              <div className="w-64 h-64 rounded-full bg-blue-500/20 blur-2xl" />
            </motion.div>

            {/* Camera viewfinder circle */}
            <div className="relative w-64 h-64 rounded-full bg-gradient-to-br from-slate-800 to-slate-900 border-4 border-slate-700 overflow-hidden">
              {/* Simulated camera view with gradient */}
              <div className="absolute inset-0 bg-gradient-to-br from-blue-900/30 via-slate-900 to-emerald-900/30" />

              {/* Face icon in center */}
              <div className="absolute inset-0 flex items-center justify-center">
                <ScanFace className="w-24 h-24 text-slate-600" />
              </div>

              {/* Scanning reticle overlay */}
              {scanning && (
                <>
                  {/* Animated scanning line */}
                  <motion.div
                    className="absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-blue-400 to-transparent"
                    animate={{
                      top: ["0%", "100%"],
                    }}
                    transition={{
                      duration: 2,
                      repeat: Infinity,
                      ease: "linear",
                    }}
                  />

                  {/* Corner brackets */}
                  <div className="absolute inset-0 p-4">
                    {/* Top-left */}
                    <div className="absolute top-4 left-4 w-12 h-12 border-l-4 border-t-4 border-blue-400" />
                    {/* Top-right */}
                    <div className="absolute top-4 right-4 w-12 h-12 border-r-4 border-t-4 border-blue-400" />
                    {/* Bottom-left */}
                    <div className="absolute bottom-4 left-4 w-12 h-12 border-l-4 border-b-4 border-blue-400" />
                    {/* Bottom-right */}
                    <div className="absolute bottom-4 right-4 w-12 h-12 border-r-4 border-b-4 border-blue-400" />
                  </div>

                  {/* Rotating border */}
                  <motion.div
                    className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-400"
                    animate={{
                      rotate: 360,
                    }}
                    transition={{
                      duration: 3,
                      repeat: Infinity,
                      ease: "linear",
                    }}
                  />
                </>
              )}

              {/* Progress ring */}
              <svg className="absolute inset-0 w-full h-full -rotate-90">
                <circle
                  cx="50%"
                  cy="50%"
                  r="48%"
                  fill="none"
                  stroke="rgb(30 41 59)"
                  strokeWidth="4"
                />
                <motion.circle
                  cx="50%"
                  cy="50%"
                  r="48%"
                  fill="none"
                  stroke="url(#gradient)"
                  strokeWidth="4"
                  strokeLinecap="round"
                  style={{
                    pathLength: progress / 100,
                  }}
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: progress / 100 }}
                  transition={{ duration: 0.3 }}
                />
                <defs>
                  <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#3b82f6" />
                    <stop offset="100%" stopColor="#10b981" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
          </div>

          {/* Status Text */}
          <div className="text-center">
            <motion.div
              className="text-lg mb-2"
              animate={{ opacity: [1, 0.6, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            >
              {progress < 100 ? "Verifying Identity..." : "Verification Complete"}
            </motion.div>
            <div className="text-slate-400 text-sm">
              Please look at the camera
            </div>
          </div>

          {/* Progress Indicator */}
          <div className="mt-6">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs text-slate-400">Progress</span>
              <span className="text-xs text-blue-400">{Math.round(progress)}%</span>
            </div>
            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-blue-500 to-emerald-500"
                style={{ width: `${progress}%` }}
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </div>

          {/* Security Features */}
          <div className="mt-6 grid grid-cols-3 gap-3">
            <div className="bg-slate-800 rounded-lg p-3 text-center">
              <div className="text-xs text-slate-400 mb-1">Liveness</div>
              <div className="text-emerald-400 text-xs">
                {progress > 30 ? "✓" : "•"}
              </div>
            </div>
            <div className="bg-slate-800 rounded-lg p-3 text-center">
              <div className="text-xs text-slate-400 mb-1">Depth</div>
              <div className="text-emerald-400 text-xs">
                {progress > 60 ? "✓" : "•"}
              </div>
            </div>
            <div className="bg-slate-800 rounded-lg p-3 text-center">
              <div className="text-xs text-slate-400 mb-1">Texture</div>
              <div className="text-emerald-400 text-xs">
                {progress > 90 ? "✓" : "•"}
              </div>
            </div>
          </div>
        </div>

        {/* Security Notice */}
        <div className="mt-6 text-center text-slate-500 text-xs">
          Your biometric data is processed locally and never stored
        </div>
      </div>
    </div>
  );
}
