import { useEffect, useRef, useCallback } from "react";
import { useUser } from "../context/UserContext";

export function useSessionTimeout(timeoutMs = 5 * 60 * 1000) {
  const { logout } = useUser();
  const ref = useRef<ReturnType<typeof setTimeout> | null>(null);

  const reset = useCallback(() => {
    if (ref.current) clearTimeout(ref.current);
    ref.current = setTimeout(() => {
      logout();
    }, timeoutMs);
  }, [logout, timeoutMs]);

  useEffect(() => {
    const events = ["mousedown", "keydown", "scroll", "touchstart", "click"];
    events.forEach((e) => document.addEventListener(e, reset, { passive: true }));
    reset();
    return () => {
      events.forEach((e) => document.removeEventListener(e, reset));
      if (ref.current) clearTimeout(ref.current);
    };
  }, [reset]);
}
