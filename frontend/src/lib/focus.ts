import { useCallback, useRef } from "react";

/** A panel opened from code (no Radix trigger) gives the keyboard focus back to what opened it on close,
 *  as a triggered dialog does; without this focus fell to <body> and a keyboard user started over at the
 *  top of the page. When the opener is gone (a floating button hides while its panel is open), the
 *  fallback element gets focus once it is back. */
export function useReturnFocus(fallback?: string) {
  const ref = useRef<HTMLElement | null>(null);
  const remember = useCallback(() => {
    const a = document.activeElement;
    ref.current = a instanceof HTMLElement && a !== document.body ? a : null;
  }, []);
  const forget = useCallback(() => {
    ref.current = null;
  }, []);
  const onCloseAutoFocus = useCallback(
    (e: Event) => {
      const el = ref.current;
      ref.current = null;
      e.preventDefault();
      if (el?.isConnected) el.focus({ preventScroll: true });
      else if (fallback) window.setTimeout(() => document.querySelector<HTMLElement>(fallback)?.focus({ preventScroll: true }), 120);
    },
    [fallback],
  );
  return { remember, forget, onCloseAutoFocus };
}
