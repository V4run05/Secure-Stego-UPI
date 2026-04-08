import { useState } from "react";
import { useNavigate } from "react-router";
import { motion, AnimatePresence } from "motion/react";
import { Shield, ArrowRight, ArrowLeft, Eye, EyeOff, UserPlus, CheckCircle2, AlertCircle } from "lucide-react";
import { WebcamCapture } from "./WebcamCapture";
import { apiClient } from "../services/api";
import { useUser } from "../context/UserContext";
import { toast } from "sonner";

type Step = 1 | 2 | 3 | 4;

interface Form {
  userId: string;
  fullName: string;
  pin: string;
  pinConfirm: string;
  faceImage: string;
}

function pinStrength(pin: string): { label: string; color: string; width: string } {
  if (!pin) return { label: "", color: "bg-slate-700", width: "w-0" };
  if (pin.length < 4) return { label: "Too short", color: "bg-red-500", width: "w-1/4" };
  if (pin.length === 4) return { label: "Fair", color: "bg-yellow-500", width: "w-2/4" };
  if (pin.length === 5) return { label: "Good", color: "bg-blue-500", width: "w-3/4" };
  return { label: "Strong", color: "bg-emerald-500", width: "w-full" };
}

export function Registration() {
  const navigate = useNavigate();
  const { setUser } = useUser();
  const [step, setStep] = useState<Step>(1);
  const [loading, setLoading] = useState(false);
  const [showPin, setShowPin] = useState(false);
  const [form, setForm] = useState<Form>({
    userId: "",
    fullName: "",
    pin: "",
    pinConfirm: "",
    faceImage: "",
  });
  const [errors, setErrors] = useState<Partial<Form & { submit: string }>>({});

  const update = (field: keyof Form, value: string) => {
    setForm((f) => ({ ...f, [field]: value }));
    setErrors((e) => ({ ...e, [field]: undefined }));
  };

  const validateStep1 = () => {
    const errs: Partial<Form> = {};
    if (!form.userId.endsWith("@upi") || form.userId.includes(" ") || form.userId !== form.userId.toLowerCase())
      errs.userId = "Must be lowercase with no spaces, e.g. alice@upi";
    if (!form.fullName.trim() || form.fullName.length < 2)
      errs.fullName = "Enter your full name";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const validateStep2 = () => {
    const errs: Partial<Form> = {};
    if (!form.pin.match(/^\d{4,6}$/))
      errs.pin = "PIN must be 4-6 digits";
    if (form.pin !== form.pinConfirm)
      errs.pinConfirm = "PINs do not match";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const validateStep3 = () => {
    if (!form.faceImage) {
      toast.error("Please capture your face photo first");
      return false;
    }
    return true;
  };

  const next = () => {
    if (step === 1 && !validateStep1()) return;
    if (step === 2 && !validateStep2()) return;
    if (step === 3 && !validateStep3()) return;
    setStep((s) => (s + 1) as Step);
  };

  const handleFaceCapture = (b64: string) => {
    update("faceImage", b64);
    toast.success("Face captured!");
  };

  const handleSubmit = async () => {
    setLoading(true);
    setErrors({});
    try {
      const result = await apiClient.register({
        user_id: form.userId,
        face_image_b64: form.faceImage,
        pin: form.pin,
      });
      if (result.success) {
        setUser({ userId: form.userId, fullName: form.fullName, isRegistered: true });
        toast.success("Registration successful!");
        navigate("/");
      } else {
        setErrors({ submit: result.error });
      }
    } catch {
      setErrors({ submit: "Network error. Please try again." });
    } finally {
      setLoading(false);
    }
  };

  const strength = pinStrength(form.pin);

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 mb-4">
            <UserPlus className="w-8 h-8" />
          </div>
          <h1 className="text-2xl mb-1">Create Account</h1>
          <p className="text-slate-400 text-sm">Step {step} of 4</p>
          <div className="flex gap-1 mt-3 justify-center">
            {([1, 2, 3, 4] as Step[]).map((s) => (
              <div
                key={s}
                className={`h-1 rounded-full transition-all ${
                  s <= step ? "bg-blue-500 w-8" : "bg-slate-700 w-4"
                }`}
              />
            ))}
          </div>
        </div>

        <div className="bg-slate-900 rounded-3xl p-6 shadow-2xl border border-slate-800">
          <AnimatePresence mode="wait">
            {step === 1 && (
              <motion.div key="step1" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <h2 className="text-lg font-medium mb-5">Your Details</h2>

                <div className="mb-4">
                  <label className="text-slate-400 text-sm mb-1.5 block">UPI ID</label>
                  <input
                    type="text"
                    value={form.userId}
                    onChange={(e) => update("userId", e.target.value.toLowerCase())}
                    placeholder="yourname@upi"
                    autoFocus
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  {errors.userId && <p className="text-red-400 text-xs mt-1 flex items-center gap-1"><AlertCircle className="w-3 h-3" />{errors.userId}</p>}
                </div>

                <div className="mb-6">
                  <label className="text-slate-400 text-sm mb-1.5 block">Full Name</label>
                  <input
                    type="text"
                    value={form.fullName}
                    onChange={(e) => update("fullName", e.target.value)}
                    placeholder="Your full name"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  {errors.fullName && <p className="text-red-400 text-xs mt-1 flex items-center gap-1"><AlertCircle className="w-3 h-3" />{errors.fullName}</p>}
                </div>

                <button onClick={next} className="w-full bg-gradient-to-r from-blue-500 to-emerald-500 text-white py-3 rounded-xl font-medium flex items-center justify-center gap-2">
                  Continue <ArrowRight className="w-4 h-4" />
                </button>
              </motion.div>
            )}

            {step === 2 && (
              <motion.div key="step2" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <h2 className="text-lg font-medium mb-5">Set Your PIN</h2>

                <div className="mb-4">
                  <label className="text-slate-400 text-sm mb-1.5 block">PIN (4-6 digits)</label>
                  <div className="relative">
                    <input
                      type={showPin ? "text" : "password"}
                      inputMode="numeric"
                      value={form.pin}
                      onChange={(e) => update("pin", e.target.value.replace(/\D/g, "").slice(0, 6))}
                      placeholder="••••••"
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 pr-12 text-xl tracking-widest"
                    />
                    <button type="button" onClick={() => setShowPin((s) => !s)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white">
                      {showPin ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                  {form.pin.length > 0 && (
                    <div className="mt-2">
                      <div className="h-1 bg-slate-700 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full transition-all ${strength.color} ${strength.width}`} />
                      </div>
                      <p className="text-xs mt-1 text-slate-400">{strength.label}</p>
                    </div>
                  )}
                  {errors.pin && <p className="text-red-400 text-xs mt-1 flex items-center gap-1"><AlertCircle className="w-3 h-3" />{errors.pin}</p>}
                </div>

                <div className="mb-6">
                  <label className="text-slate-400 text-sm mb-1.5 block">Confirm PIN</label>
                  <input
                    type="password"
                    inputMode="numeric"
                    value={form.pinConfirm}
                    onChange={(e) => update("pinConfirm", e.target.value.replace(/\D/g, "").slice(0, 6))}
                    placeholder="••••••"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 text-xl tracking-widest"
                  />
                  {errors.pinConfirm && <p className="text-red-400 text-xs mt-1 flex items-center gap-1"><AlertCircle className="w-3 h-3" />{errors.pinConfirm}</p>}
                </div>

                <div className="flex gap-3">
                  <button onClick={() => setStep(1)} className="flex-1 bg-slate-800 border border-slate-700 text-white py-3 rounded-xl font-medium flex items-center justify-center gap-2 hover:border-slate-500">
                    <ArrowLeft className="w-4 h-4" /> Back
                  </button>
                  <button onClick={next} className="flex-1 bg-gradient-to-r from-blue-500 to-emerald-500 text-white py-3 rounded-xl font-medium flex items-center justify-center gap-2">
                    Continue <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            )}

            {step === 3 && (
              <motion.div key="step3" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <h2 className="text-lg font-medium mb-5">Face Capture</h2>
                <WebcamCapture onCapture={handleFaceCapture} showFaceGuide />
                <div className="flex gap-3 mt-4">
                  <button onClick={() => setStep(2)} className="flex-1 bg-slate-800 border border-slate-700 text-white py-3 rounded-xl font-medium flex items-center justify-center gap-2 hover:border-slate-500">
                    <ArrowLeft className="w-4 h-4" /> Back
                  </button>
                  {form.faceImage && (
                    <button onClick={next} className="flex-1 bg-gradient-to-r from-blue-500 to-emerald-500 text-white py-3 rounded-xl font-medium flex items-center justify-center gap-2">
                      Continue <ArrowRight className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </motion.div>
            )}

            {step === 4 && (
              <motion.div key="step4" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <h2 className="text-lg font-medium mb-5">Review & Register</h2>

                <div className="bg-slate-800 rounded-2xl p-4 mb-6 space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400 text-sm">UPI ID</span>
                    <span className="font-medium">{form.userId}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400 text-sm">Full Name</span>
                    <span className="font-medium">{form.fullName}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400 text-sm">PIN</span>
                    <span className="font-medium tracking-widest">{"•".repeat(form.pin.length)}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400 text-sm">Face</span>
                    <span className="flex items-center gap-1 text-emerald-400 text-sm">
                      <CheckCircle2 className="w-4 h-4" /> Captured
                    </span>
                  </div>
                </div>

                {errors.submit && (
                  <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center gap-2">
                    <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                    <p className="text-red-300 text-sm">{errors.submit}</p>
                  </div>
                )}

                <div className="flex gap-3">
                  <button onClick={() => setStep(3)} disabled={loading} className="flex-1 bg-slate-800 border border-slate-700 text-white py-3 rounded-xl font-medium flex items-center justify-center gap-2 hover:border-slate-500 disabled:opacity-50">
                    <ArrowLeft className="w-4 h-4" /> Back
                  </button>
                  <button
                    onClick={handleSubmit}
                    disabled={loading}
                    className="flex-1 bg-gradient-to-r from-blue-500 to-emerald-500 text-white py-3 rounded-xl font-medium flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {loading ? (
                      <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Registering…</>
                    ) : (
                      <><Shield className="w-4 h-4" /> Register</>
                    )}
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <p className="text-center text-slate-500 text-xs mt-6">
          Already have an account?{" "}
          <button onClick={() => navigate("/")} className="text-blue-400 hover:underline">
            Go to payments
          </button>
        </p>
      </div>
    </div>
  );
}
