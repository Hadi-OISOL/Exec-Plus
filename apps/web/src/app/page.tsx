/* Use case: The public Syntelio website at the root route.
What it does: Opens on a green field with the claim that every number comes with a receipt and prints a real one, then offers the live sample question on paper, the four stages, the ten analysts, the three things that arrive with an answer, the open questions, the closing field and the quiet footer line, all linking to the sign-up and log-in pages. */

import Link from "next/link";
import styles from "./page.module.css";
import { AnalystSentence } from "./site/analysts";
import { AskSample } from "./site/ask-sample";
import { Shot } from "./site/shot";
import { PrintReveal, Receipt } from "./site/kit";
import { Stages } from "./site/stages";

const rainfall = [["West", "1,744.51", 1744.51], ["North", "1,599.96", 1599.96], ["South", "1,567.74", 1567.74], ["Central", "1,562.96", 1562.96], ["East", "1,310.04", 1310.04]] as const;

const arrives = [
  { title: "Numbers from a read-only engine", text: "Every figure comes from a validated query executed against your data. The model never supplies or rounds a number.", caption: "Average electrical conductivity by region, double-checked by a second query.", shot: "feat-engine", alt: "A double-checked finding: average electrical conductivity by region, Central highest at 2.22 dS/m, as a bar chart", ratio: "1110 / 720" },
  { title: "Lineage on every answer", text: "Each answer carries the dataset version, operation, filters and row count, so a result can be replayed and checked months later.", caption: "The analyst overview: 100 rows confirmed by a separate count, 20 columns, 6 measures.", shot: "feat-lineage", alt: "The analyst overview counts: 100 rows checked by a separate count query, 20 columns, 6 measures analysed", ratio: "1120 / 530" },
  { title: "Forecasts and what-ifs, with their working", text: "Dated series are projected with measured error and compared with what actually arrived. A what-if states its assumption and computes the exact result; nothing is predicted from it.", caption: "A saved what-if: 2 mm more irrigation a day for ten days adds exactly 20 mm.", shot: "feat-forecast", alt: "A saved what-if on the farm file: starting total 6,575.6 mm of previous irrigation, and 6,595.6 mm after adding 2 mm a day for ten days, a change of 20 mm", ratio: "1430 / 240" },
] as const;

const questions = [
  ["Does the AI calculate the numbers?", "No. A language model only interprets your question and words the explanation. A read-only query engine computes every figure, and each answer shows the dataset, operation, filters and row count it used."],
  ["Which files and sources work?", "CSV, TSV, Excel (xlsx, xls, xlsb, ods), JSON and NDJSON, Parquet, SQLite, SPSS, Stata, SAS, XML and zipped versions of these, up to 500 MB per file. Read-only connections to PostgreSQL, MySQL/MariaDB and SQL Server, plus Google Sheets import, are included."],
  ["Which languages can I ask in?", "English, Urdu and Roman Urdu. When a request could mean more than one thing, Syntelio asks a clarifying question instead of guessing."],
  ["Who can see my data?", "Only members of your workspace, with the roles you give them. Every question, answer and export is recorded in the workspace audit history."],
  ["Can I trust a forecast?", "Forecasts are labelled estimates with their measured error and the method used. Syntelio never presents a projection as a fact, and compares it with actual values once they arrive."],
  ["What does it cost?", "Creating an account is free. Each account includes 5 GB of storage and files up to 500 MB."],
] as const;

const delay = (index: number) => ({ "--i": index } as React.CSSProperties);

function HeroReceipt() {
  return <Receipt
    className={styles.printer}
    frame="printer"
    question="Which region had the most rainfall on average?"
    figure="1,744.51"
    unit="mm"
    figureLabel="West, mean Rainfall_mm across its 18 fields."
    bars={rainfall.map(([label, value, raw]) => ({ label, value, share: raw / rainfall[0][2], emphasis: label === "West" }))}
    barsLabel="Average rainfall by region, millimetres"
    footer={[
      { label: "Dataset", value: "test_100rows.csv · version 1" },
      { label: "Operation", value: "AVG(Rainfall_mm) by Region" },
      { label: "Filters", value: "none" },
      { label: "Rows read", value: "100 of 100 · 20 columns" },
      { label: "Replayable", value: "yes" },
    ]}
    ariaLabel="Receipt: Which region had the most rainfall on average?"
  />;
}

export default function Home() {
  return (
    <div className={styles.site}>
      <script dangerouslySetInnerHTML={{ __html: `document.documentElement.classList.add("js")` }} />
      <PrintReveal />
      <div className={styles.field}>
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
        <section className={`${styles.frame} ${styles.hero}`} aria-label="Syntelio">
          <div>
            <h1 className={styles.heroLine}>Every number comes with a <em>receipt.</em></h1>
            <p className={styles.lead}>Upload a spreadsheet or connect your database. Ten analysts read it, you ask the rest in plain words, and a read-only engine computes every figure; the model never does.</p>
            <div className={styles.heroActions}>
              <Link href="/signup" className={styles.button}>Create a free account</Link>
              <a href="#try" className={`${styles.button} ${styles.buttonGhost}`}>See a sample answer</a>
            </div>
            <p className={styles.langs}>Also understands: <b lang="ur" dir="rtl">اردو</b> · <b lang="ur-Latn">Roman Urdu</b></p>
          </div>
          <HeroReceipt />
        </section>
      </div>

      <main>
        <div className={styles.band}><section className={`${styles.frame} ${styles.section}`} id="try">
          <h2 data-reveal="">Try it on a 100‑row farm file</h2>
          <p className={styles.sectionNote} data-reveal="" style={delay(1)}>Four questions are prepared here, in English and Roman Urdu; the product takes any question and prints the same kind of receipt.</p>
          <div data-reveal="" style={delay(2)}><AskSample /></div>
        </section></div>

        <section className={`${styles.frame} ${styles.section}`} id="how">
          <h2 data-reveal="">From file to answer in four stages</h2>
          <Stages />
        </section>

        <section className={`${styles.frame} ${styles.analysts}`} aria-labelledby="analysts-heading">
          <h2 id="analysts-heading" data-reveal="">Ten analysts read it before you ask</h2>
          <div data-reveal="" style={delay(1)}><AnalystSentence /></div>
        </section>

        <div className={styles.band}><section className={`${styles.frame} ${styles.section}`} id="arrives">
          <h2 data-reveal="">What arrives with the answer</h2>
          <ul className={styles.papers}>
            {arrives.map((paper, index) => (
              <li key={paper.title} className={styles.paperCard} data-reveal="" style={{ "--i": index, "--ratio": paper.ratio } as React.CSSProperties}>
                <Shot name={paper.shot} alt={paper.alt} width={560} height={300} />
                <h3>{paper.title}</h3>
                <p>{paper.text}</p>
                <p className={styles.caption}>{paper.caption}</p>
              </li>
            ))}
          </ul>
        </section></div>

        <section className={`${styles.frame} ${styles.section}`} id="questions">
          <ul className={styles.faqRows}>
            <li className={styles.faqRow}><h2>Questions, answered</h2></li>
            {questions.map(([question, answer]) => (
              <li key={question} className={styles.faqRow}><h3 data-reveal="">{question}</h3><p data-reveal="" style={delay(1)}>{answer}</p></li>
            ))}
          </ul>
        </section>

        <section className={`${styles.field} ${styles.close}`} aria-labelledby="close-heading">
          <h2 id="close-heading" className={styles.closeLine}>Your first <em>receipt</em> is a file away.</h2>
          <p>Accounts are free, with 5 GB of storage and files up to 500 MB.</p>
          <div className={styles.closeChoice}>
            <Link href="/signup" className={styles.button}>Create a free account</Link>
            <Link href="/login" className={`${styles.button} ${styles.buttonGhost}`}>Log in</Link>
          </div>
        </section>
      </main>

      <footer className={styles.footer}>
        <span>Syntelio · Synthesized Enterprise Intelligence</span>
        <nav aria-label="Footer"><Link href="/login">Log in</Link><Link href="/signup">Create account</Link><a href="#questions">Security &amp; privacy</a></nav>
        <span>© {new Date().getFullYear()} · Pakistan and beyond</span>
      </footer>
    </div>
  );
}
