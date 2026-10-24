/* Use case: Lets a reviewer choose a measured false-alarm target for anomaly detectors.
What it does: Offers the registered targets and shows the saved synthetic calibration evidence without browser arithmetic. */

export type FalseAlarmTarget = "" | "0.05" | "0.01" | "0.005";
export type DetectorCalibration = {
  target_false_alarm_rate: string;
  threshold: string;
  measured_false_alarm_rate: Record<string, string>;
  label: string;
};

export function FalseAlarmTargetSelect({ value, onChange, disabled, noun = "normal values" }: { value: FalseAlarmTarget; onChange: (value: FalseAlarmTarget) => void; disabled?: boolean; noun?: string }) {
  return <label>False-alarm target · sets the threshold
    <select value={value} disabled={disabled} onChange={event => onChange(event.target.value as FalseAlarmTarget)}>
      <option value="">No target · use my threshold</option>
      <option value="0.05">{`About 5 in 100 ${noun} flagged`}</option>
      <option value="0.01">{`About 1 in 100 ${noun} flagged`}</option>
      <option value="0.005">{`About 1 in 200 ${noun} flagged`}</option>
    </select>
  </label>;
}

export function CalibrationNote({ value }: { value?: DetectorCalibration }) {
  if (!value) return null;
  const rates = Object.entries(value.measured_false_alarm_rate).map(([family, rate]) => `${family.replaceAll("_", " ")} ${rate}`).join(" · ");
  return <p className="chartCaption">False-alarm target {value.target_false_alarm_rate} → threshold {value.threshold}. Measured on synthetic unchanged data: {rates}. {value.label}</p>;
}
