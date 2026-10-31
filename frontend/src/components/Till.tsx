import { useEffect, useRef, useState } from "react";
import { money } from "../money";

const START_CASH = 3400;
const BUFFER = 100;

/** Register digits that tick down when a check clears. */
function useTicker(target: number | null) {
  const [shown, setShown] = useState(target ?? 0);
  const from = useRef(shown);
  const seen = useRef(false);
  useEffect(() => {
    if (target === null) return;
    if (!seen.current) {
      // First reading: just show it. Only later changes (a check clearing) tick.
      seen.current = true;
      setShown(target);
      return;
    }
    from.current = shown;
    const start = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / 1100);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(from.current + (target - from.current) * eased);
      if (p < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);
  return shown;
}

/** Checking balance in the top bar: big glowing digits, the $100 buffer bar, and a pop-out chip when money leaves. */
export function CashCounter({ checking }: { checking: number | null }) {
  const shown = useTicker(checking);
  const scale = Math.max(START_CASH, checking ?? 0);
  const pct = (n: number) => `${Math.max(0, Math.min(100, (n / scale) * 100))}%`;
  const low = checking !== null && checking < BUFFER;
  const prev = useRef<number | null>(null);
  const [delta, setDelta] = useState<{ amount: number; key: number } | null>(null);
  useEffect(() => {
    if (checking === null) return;
    if (prev.current !== null && checking !== prev.current) {
      setDelta({ amount: checking - prev.current, key: Date.now() });
      const done = setTimeout(() => setDelta(null), 3500);
      prev.current = checking;
      return () => clearTimeout(done);
    }
    prev.current = checking;
  }, [checking]);
  return (
    <div className={`cash-counter ${low ? "cash-low" : ""} ${delta ? "cash-pulse" : ""}`}
      title="Checking (cash_accounts). Cash only goes out; every dollar needs a human signature.">
      <span className="cash-label">Checking <span className="cash-sub">cash on hand</span></span>
      <span className="cash-digits" aria-live="polite">{money(shown)}</span>
      <span className="cash-bar" aria-hidden="true">
        <span className="cash-fill" style={{ width: pct(checking ?? 0) }} />
        <span className="cash-buffer" style={{ left: pct(BUFFER) }} />
      </span>
      <span className="cash-foot">{low ? "Below our $100 buffer" : `$100 buffer · ${money(Math.max((checking ?? 0) - BUFFER, 0))} free`}</span>
      {delta && (
        <span key={delta.key} className={`cash-delta ${delta.amount < 0 ? "cash-out" : "cash-in"}`}>
          {delta.amount < 0 ? "−" : "+"}{money(Math.abs(delta.amount))}
        </span>
      )}
    </div>
  );
}
