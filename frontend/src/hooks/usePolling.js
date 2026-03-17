import { useEffect, useRef } from "react";

export function usePolling(callback, intervalMs, enabled = true) {
  const callbackRef = useRef(callback);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled || intervalMs <= 0) {
      return undefined;
    }

    const timer = setInterval(() => {
      callbackRef.current();
    }, intervalMs);

    return () => clearInterval(timer);
  }, [intervalMs, enabled]);
}
