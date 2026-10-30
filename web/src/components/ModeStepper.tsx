import { useTranslation } from "react-i18next";
import { STUDY_MODES, type StudyMode } from "../study";

/** The four study modes as steps: own language, side by side, German with help, German only.
 * The current step is highlighted; any step can be chosen, and "One step back" is always there
 * (PLAN.md: the learner can always step back a mode). */

interface Props {
  mode: StudyMode;
  onChange: (mode: StudyMode) => void;
  /** Shown as reached up to this mode. */
  reached?: StudyMode;
  disabled?: boolean;
  /** The question has no approved translation in the learner's language. */
  fallback?: boolean;
}

export default function ModeStepper({ mode, onChange, reached, disabled, fallback }: Props) {
  const { t } = useTranslation();
  const current = STUDY_MODES.indexOf(mode);
  const upTo = Math.max(current, reached ? STUDY_MODES.indexOf(reached) : current);
  return (
    <div className="mode-stepper">
      <ol className="mode-steps" aria-label={t("study.modesLabel")}>
        {STUDY_MODES.map((m, i) => (
          <li key={m}>
            <button
              type="button"
              className={`mode-step${i === current ? " current" : ""}${i <= upTo ? " reached" : ""}`}
              aria-current={i === current ? "step" : undefined}
              disabled={disabled}
              onClick={() => i !== current && onChange(m)}
            >
              <span className="mode-num" aria-hidden="true">
                {i + 1}
              </span>
              <span className="mode-name">{t(`study.mode.${m}`)}</span>
            </button>
          </li>
        ))}
      </ol>
      <div className="mode-tools">
        {current > 0 && (
          <button type="button" className="link-btn small" disabled={disabled} onClick={() => onChange(STUDY_MODES[current - 1])}>
            {"←"} {t("study.stepBack")}
          </button>
        )}
        {fallback && <span className="small muted">{t("study.fallback")}</span>}
      </div>
    </div>
  );
}
