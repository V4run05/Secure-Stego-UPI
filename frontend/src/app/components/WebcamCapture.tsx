import { useRef, useState, useCallback } from "react";
import Webcam from "react-webcam";
import { Camera, CameraOff, RefreshCw } from "lucide-react";

interface WebcamCaptureProps {
  onCapture: (imageBase64: string) => void;
  showFaceGuide?: boolean;
}

export function WebcamCapture({ onCapture, showFaceGuide = true }: WebcamCaptureProps) {
  const webcamRef = useRef<Webcam>(null);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [captured, setCaptured] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUserMedia = () => {
    setHasPermission(true);
    setError(null);
  };

  const handleUserMediaError = (err: string | DOMException) => {
    setHasPermission(false);
    const msg = typeof err === "string" ? err : err.message;
    setError(msg.includes("Permission") ? "Camera permission denied." : "Camera not available.");
  };

  const capture = useCallback(() => {
    const src = webcamRef.current?.getScreenshot();
    if (src) {
      setCaptured(src);
      const b64 = src.split(",")[1] ?? src;
      onCapture(b64);
    }
  }, [onCapture]);

  const retake = () => setCaptured(null);

  if (hasPermission === false) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center gap-4">
        <CameraOff className="w-12 h-12 text-red-400" />
        <p className="text-red-300 font-medium">Camera Access Denied</p>
        <p className="text-slate-400 text-sm">{error}</p>
        <p className="text-slate-500 text-xs">Enable camera in browser settings and reload.</p>
      </div>
    );
  }

  if (captured) {
    return (
      <div className="flex flex-col gap-4">
        <img
          src={captured}
          alt="Captured"
          className="rounded-2xl w-full border-2 border-emerald-500/50"
        />
        <button
          onClick={retake}
          className="flex items-center justify-center gap-2 w-full bg-slate-800 border border-slate-700 hover:border-slate-500 text-white py-3 rounded-xl transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retake Photo
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="relative rounded-2xl overflow-hidden bg-slate-900 border border-slate-700">
        <Webcam
          ref={webcamRef}
          screenshotFormat="image/jpeg"
          videoConstraints={{ width: 640, height: 480, facingMode: "user" }}
          onUserMedia={handleUserMedia}
          onUserMediaError={handleUserMediaError}
          mirrored
          className="w-full"
          screenshotQuality={0.92}
        />

        {showFaceGuide && hasPermission && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-40 h-52 border-4 border-blue-400/70 rounded-full" />
          </div>
        )}

        {hasPermission === null && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-950/80">
            <Camera className="w-10 h-10 text-slate-400 animate-pulse" />
            <p className="text-slate-300 text-sm">Requesting camera access…</p>
          </div>
        )}
      </div>

      {hasPermission && (
        <>
          {showFaceGuide && (
            <p className="text-slate-400 text-xs text-center">
              Position your face inside the oval guide
            </p>
          )}
          <button
            onClick={capture}
            aria-label="Capture face photo for verification"
            className="flex items-center justify-center gap-2 w-full bg-gradient-to-r from-blue-500 to-emerald-500 text-white py-3 rounded-xl font-medium hover:opacity-90 transition-opacity"
          >
            <Camera className="w-5 h-5" />
            Capture Photo
          </button>
        </>
      )}
    </div>
  );
}
