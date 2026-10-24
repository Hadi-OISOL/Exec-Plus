/* Animated activity represents a recorded operation, never a model's private reasoning. */
import styles from "./request-progress.module.css";

export function RequestProgress({ title, detail, paused = false }: {
  title: string;
  detail: string;
  paused?: boolean;
}) {
  return <div className={styles.progress} data-paused={paused}>
    <div className={styles.orbit} aria-hidden="true">
      <span /><span /><span /><i />
    </div>
    <div className={styles.copy} role="status" aria-atomic="true">
      <span className={styles.label}>Syntelio</span>
      <p>{title}</p>
      <small>{detail}</small>
    </div>
  </div>;
}
