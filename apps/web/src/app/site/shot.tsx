/* Use case: A real interface picture on the public website.
What it does: Renders the light and dark crops of one product screenshot; the stylesheet shows the one that matches the reader's theme. */

import styles from "../page.module.css";

type Props = { name: string; alt: string; width: number; height: number; priority?: boolean; className?: string; style?: React.CSSProperties };

export function Shot({ name, alt, width, height, priority, className, style }: Props) {
  return <span className={`${styles.shot} ${className ?? ""}`} style={style} data-ui="">
    <img className={styles.shotLight} src={`/marketing/${name}-light.webp`} alt={alt} width={width} height={height} fetchPriority={priority ? "high" : undefined} />
    <img className={styles.shotDark} src={`/marketing/${name}-dark.webp`} alt={alt} width={width} height={height} fetchPriority={priority ? "high" : undefined} />
  </span>;
}
