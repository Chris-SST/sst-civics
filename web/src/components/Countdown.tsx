import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

/** Time left until a server deadline. `serverNow` corrects for a device clock that is off; the
 * server refuses answers after the deadline in any case. Announces five minutes and one minute
 * left to screen readers, not every second. */

interface Props {
  deadline: string;
  serverNow: string;
  onExpire?: () => void;
}

function format(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export default function Countdown({ deadline, serverNow, onExpire }: Props) {
  const { t } = useTranslation();
  const offset = useRef(Date.parse(serverNow) - Date.now());
  const end = Date.parse(deadline);
  const [seconds, setSeconds] = useState(() => (end - (Date.now() + offset.current)) / 1000);
  const fired = useRef(false);
  const expire = useRef(onExpire);
  expire.current = onExpire;

  useEffect(() => {
    offset.current = Date.parse(serverNow) - Date.now();
  }, [serverNow]);

  useEffect(() => {
    const tick = () => {
      const s = (end - (Date.now() + offset.current)) / 1000;
      setSeconds(s);
      if (s <= 0 && !fired.current) {
        fired.current = true;
        expire.current?.();
      }
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [end]);

  const warn = seconds <= 300;
  const announce = seconds <= 0 ? t("mock.timeUp") : seconds <= 60 ? t("mock.oneMinuteLeft") : seconds <= 300 ? t("mock.fiveMinutesLeft") : "";
  return (
    <div className={`countdown${warn ? " countdown-warn" : ""}`} role="timer">
      <span className="small">{t("mock.timeLeft")}</span>
      <span className="countdown-time">{format(seconds)}</span>
      <span className="visually-hidden" aria-live="polite">
        {announce}
      </span>
    </div>
  );
}
