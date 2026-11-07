/* Use case: The tape of real answers that runs under the public-site hero.
What it does: Prints six exact precomputed results from farm_field_survey.csv as one continuous paper strip; the strip travels slowly when motion is allowed and stands still otherwise, with the repeat copy hidden from assistive technology. */

import styles from "../page.module.css";

const answers = [
  ["Which region had the most rain?", "West · AVG(Rainfall_mm) 1,744.51"],
  ["Average soil pH by crop", "Rice · AVG(Soil_pH) 6.69"],
  ["Which crop has the largest fields?", "Wheat · AVG(Field_Area_hectare) 9.29"],
  ["Drip irrigation kitne kheton mein hai?", "COUNT(rows) by Irrigation_Type · Drip 19 of 100"],
  ["How many fields are canal-fed?", "Canal 31 · Sprinkler 26 · Rainfed 24"],
  ["Where does this come from?", "farm_field_survey.csv · version 1 · 100 of 100 rows read"],
] as const;

function Strip({ hidden }: { hidden?: boolean }) {
  return <ul className={styles.tickerList} aria-hidden={hidden || undefined}>
    {answers.map(([question, answer]) => <li key={question} className={styles.tickerItem}><i className={styles.tickerQuestion}>{question}</i><span className={styles.tickerAnswer}>{answer}</span></li>)}
  </ul>;
}

export function Ticker() {
  return <div className={styles.ticker} aria-label="Recent answers from the sample file">
    <div className={styles.tickerTrack}><Strip /><Strip hidden /></div>
  </div>;
}
