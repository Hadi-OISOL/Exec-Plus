/* Use case: The public Syntelio website at the root route.
What it does: Sets the hero sentence with a real answer chart inside it, the live sample question, the stage slider, the analyst sentence, the evidence rows with real interface crops, the open questions, the closing choice and the quiet footer line, all linking to the sign-up and log-in pages. */

import Link from "next/link";
import styles from "./page.module.css";
import { AnalystSentence } from "./site/analysts";
import { AskSample } from "./site/ask-sample";
import { Shot } from "./site/shot";
import { SiteMotion } from "./site/site-motion";
import { Stages } from "./site/stages";

const evidence = [
  { title: "Numbers from a read-only engine", text: "Every figure comes from a validated query executed against your data. The model never supplies or rounds a number.", shot: "feat-engine", alt: "A double-checked finding: average electrical conductivity by region, Central highest at 2.22 dS/m, as a bar chart", w: "420px", ratio: [1110, 720], phone: "100%" },
  { title: "Lineage on every answer", text: "Each answer carries the dataset version, operation, filters and row count, so a result can be replayed and checked months later.", shot: "feat-lineage", alt: "The analyst overview counts: 100 rows checked by a separate count query, 20 columns, 6 measures analysed", w: "360px", ratio: [1120, 530], phone: "70%", align: "end" },
  { title: "Forecasts and what‑ifs, with their working", text: "Dated series are projected with measured error and compared with what actually arrived. A what-if states its assumption, here 2 mm more irrigation a day for ten days, and computes the exact result; nothing is predicted from it.", shot: "feat-forecast", alt: "A saved what-if on the farm file: starting total 6,575.6 mm of previous irrigation, and 6,595.6 mm after adding 2 mm a day for ten days, a change of 20 mm", w: "400px", ratio: [1430, 240], phone: "100%" },
  { title: "Unusual values, with sensible defaults", text: "Outliers and grouped or seasonal deviations are flagged across every measure, and you can set alerts on the ones you care about.", shot: "feat-unusual", alt: "The closest-to-unusual list: three rows named with their values and the usual range for their column", w: "520px", ratio: [2160, 300], phone: "100%" },
  { title: "Your data stays in your workspace", text: "Workspaces are isolated. Roles decide who sees which datasets, and the audit history records every question, export and change.", shot: "feat-workspace", alt: "The workspace settings: create a workspace with a name and a seat limit", w: "340px", ratio: [1238, 700], phone: "70%", align: "end" },
] as const;

const questions = [
  ["Does the AI calculate the numbers?", "No. A language model only interprets your question and words the explanation. A read-only query engine computes every figure, and each answer shows the dataset, operation, filters and row count it used."],
  ["Which files and sources work?", "CSV, TSV, Excel (xlsx, xls, xlsb, ods), JSON and NDJSON, Parquet, SQLite, SPSS, Stata, SAS, XML and zipped versions of these, up to 500 MB per file. Read-only connections to PostgreSQL, MySQL/MariaDB and SQL Server, plus Google Sheets import, are included."],
  ["Which languages can I ask in?", "English, Urdu and Roman Urdu. When a request could mean more than one thing, Syntelio asks a clarifying question instead of guessing."],
  ["Who can see my data?", "Only members of your workspace, with the roles you give them. Every question, answer and export is recorded in the workspace audit history."],
  ["Can I trust a forecast?", "Forecasts are labelled estimates with their measured error and the method used. Syntelio never presents a projection as a fact, and compares it with actual values once they arrive."],
  ["What does it cost?", "Creating an account is free. Each account includes 5 GB of storage and files up to 500 MB."],
] as const;

export default function Home() {
  return (
    <div className={styles.site}>
      <script dangerouslySetInnerHTML={{ __html: `document.documentElement.classList.add("js")` }} />
      <SiteMotion />
      <header className={`${styles.frame} ${styles.nav}`}>
        <Link className={styles.brand} href="/" aria-label="Syntelio home"><span className={styles.mark} aria-hidden="true">S</span>Syntelio</Link>
        <nav aria-label="Site" className={styles.navLinks}>
          <a className={styles.textLink} href="#try">Try it</a><a className={styles.textLink} href="#how">How it works</a><a className={styles.textLink} href="#questions">Questions</a>
        </nav>
        <div className={styles.navAction}>
          <Link href="/login" className={styles.textLink}>Log in</Link>
          <Link href="/signup" className={styles.button}>Create a free account</Link>
        </div>
      </header>

      <main>
        <section className={`${styles.frame} ${styles.hero}`} aria-label="Syntelio">
          <h1 className={styles.heroLine}>
            <span className={styles.line}><span style={{ "--i": 0 } as React.CSSProperties}>Ask your data.</span></span>
            <span className={styles.line}><span style={{ "--i": 1 } as React.CSSProperties}>See the <span className={styles.slot}><Shot name="slot-bars" alt="A real Syntelio answer: average electrical conductivity by region as five bars, Central highest at 2.22 and North lowest at 1.42" width={450} height={190} priority /></span></span></span>
          </h1>
          <div className={styles.heroFoot}>
            <p className={styles.lead} data-load="" style={{ "--d": "420ms" } as React.CSSProperties}>Syntelio reads your spreadsheet or database and answers plain questions in English, Urdu or Roman Urdu. A read-only engine computes every number; the model never does.</p>
            <div className={styles.heroActions} data-load="" style={{ "--d": "500ms" } as React.CSSProperties}>
              <Link href="/signup" className={styles.button}>Create a free account</Link>
              <a href="#how" className={styles.textLink}>How it works</a>
            </div>
          </div>
        </section>

        <section className={`${styles.frame} ${styles.section} ${styles.try}`} id="try">
          <h2 data-reveal="">Try it on a 100‑row farm file</h2>
          <p className={styles.sectionNote} data-reveal="" style={{ "--i": 1 } as React.CSSProperties}>test_100rows.csv has Soil, Crop, Rainfall and Region columns for 100 fields. Four questions are prepared here, in English and Roman Urdu; the product takes any question.</p>
          <div data-reveal="" style={{ "--i": 2 } as React.CSSProperties}><AskSample /></div>
        </section>

        <section className={`${styles.frame} ${styles.section}`} id="how">
          <h2 data-reveal="">From file to answer in four stages</h2>
          <Stages />
        </section>

        <section className={`${styles.frame} ${styles.analysts}`} aria-labelledby="analysts-heading">
          <h2 id="analysts-heading" data-reveal="">Ten analysts, before you ask</h2>
          <div data-reveal="" style={{ "--i": 1 } as React.CSSProperties}><AnalystSentence /></div>
        </section>

        <section className={`${styles.frame} ${styles.section}`} id="defend">
          <div className={styles.defendHead}><h2 data-reveal="">Built for numbers you can defend</h2></div>
          <ul className={styles.rows}>
            {evidence.map(row => (
              <li key={row.title} className={styles.row} style={{ "--w": row.w, "--ratio": `${row.ratio[0]} / ${row.ratio[1]}`, "--phone-w": row.phone, "--phone-align": "align" in row ? row.align : "start" } as React.CSSProperties}>
                <div className={styles.rowText}><h3 data-reveal="">{row.title}</h3><p data-reveal="" style={{ "--i": 1 } as React.CSSProperties}>{row.text}</p></div>
                <Shot name={row.shot} alt={row.alt} width={row.ratio[0] / 2} height={row.ratio[1] / 2} />
              </li>
            ))}
          </ul>
        </section>

        <section className={`${styles.frame} ${styles.section}`} id="questions">
          <ul className={styles.faqRows}>
            <li className={styles.faqRow}><h2>Questions, answered</h2></li>
            {questions.map(([question, answer]) => (
              <li key={question} className={styles.faqRow}><h3 data-reveal="">{question}</h3><p data-reveal="" style={{ "--i": 1 } as React.CSSProperties}>{answer}</p></li>
            ))}
          </ul>
        </section>

        <section className={styles.close} aria-labelledby="close-heading">
          <h2 id="close-heading" className={styles.closeLine}><span>New here,</span><span>or back?</span></h2>
          <div className={styles.closeMid}>
            <div className={styles.closeChoice}>
              <Link href="/signup" className={styles.button}>Create a free account</Link>
              <span>or</span>
              <Link href="/login" className={`${styles.button} ${styles.buttonPale}`}>Log in</Link>
            </div>
            <p>Accounts are free, with 5 GB of storage and files up to 500 MB.</p>
          </div>
        </section>
      </main>

      <footer className={styles.footer}>
        <span>Syntelio · Synthesized Enterprise Intelligence</span>
        <nav aria-label="Footer"><Link href="/login">Log in</Link><Link href="/signup">Create account</Link><a href="#defend">Security &amp; privacy</a></nav>
        <span>© {new Date().getFullYear()} · Pakistan and beyond</span>
      </footer>
    </div>
  );
}
