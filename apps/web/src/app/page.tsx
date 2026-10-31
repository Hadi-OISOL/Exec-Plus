/* Use case: The public Syntelio website at the root route.
What it does: Presents what the product does today with a navigation bar, product preview, shipped features, how it works, trust details, FAQ and sign-up calls to action. */

import Link from "next/link";
import styles from "./page.module.css";

const features = [
  ["Ask in plain language", "Type a question in English, Urdu or Roman Urdu. Syntelio turns it into a governed query, asks when something is ambiguous and keeps the thread for follow-ups."],
  ["An analyst overview, automatically", "Right after upload, several deterministic analysts check trends, segments, distributions and unusual values, cross-check each other and present the findings with charts."],
  ["Charts and dashboards", "Every dataset gets an automatic dashboard. Save answers, pin them to boards, filter and drill into the rows behind any number."],
  ["Forecasts and what-if", "Project daily or monthly series with measured accuracy, compare forecasts with what actually happened and test scenarios with stated assumptions."],
  ["Unusual-value checks", "Spot outliers, grouped and seasonal deviations with sensible defaults, and set alerts on the measures you care about."],
  ["Export and share", "Download answers and dashboards as PDF or Excel with their evidence, schedule refreshes from staged files and share saved work inside your workspace."],
] as const;

const steps = [
  ["Add your data", "Upload a CSV, Excel, JSON, Parquet, SQLite, SPSS, Stata, SAS or XML file up to 500 MB, or connect read-only to PostgreSQL, MySQL, SQL Server or a Google Sheet."],
  ["Confirm what it means", "Syntelio profiles every column, suggests roles and units, and asks only about what it could not infer."],
  ["Read the overview", "Findings, charts and suggested questions appear without prompting, each with the rows and operation behind it."],
  ["Ask, forecast, export", "Keep asking in your own words, run forecasts and what-ifs, then export or share the results."],
] as const;

const faq = [
  ["Does the AI calculate the numbers?", "No. A language model only interprets your question and words the explanation. A read-only query engine computes every figure, and each answer shows the dataset, operation, filters and row count it used."],
  ["Which files and sources work?", "CSV, TSV, Excel (xlsx, xls, xlsb, ods), JSON and NDJSON, Parquet, SQLite, SPSS, Stata, SAS, XML and zipped versions of these, up to 500 MB per file. Read-only connections to PostgreSQL, MySQL/MariaDB and SQL Server, plus Google Sheets import, are included."],
  ["Which languages can I ask in?", "English, Urdu and Roman Urdu. Clarifying questions are asked when a request could mean more than one thing."],
  ["Who can see my data?", "Only members of your workspace, with the roles you give them. Every question, answer and export is recorded in the workspace audit history."],
  ["Can I trust a forecast?", "Forecasts are labelled estimates with their measured error and the method used. Syntelio never presents a projection as a fact, and compares it with actual values once they arrive."],
  ["What does it cost?", "Creating an account is free. Each account includes 5 GB of storage and files up to 500 MB."],
] as const;

const bars = [["North", 92], ["Central", 74], ["South", 61], ["West", 38]] as const;

function Preview() {
  return (
    <div className={styles.preview} aria-label="Preview of a Syntelio workspace" role="img">
      <div className={styles.previewBar}><span /><span /><span /><em>orders_2026.xlsx · 48,120 rows · 14 columns</em></div>
      <div className={styles.previewBody}>
        <div className={styles.previewChat}>
          <p className={styles.previewQuestion}>Which region grew fastest last quarter?</p>
          <div className={styles.previewAnswer}>
            <p><strong>North</strong> grew fastest: revenue rose 18.4% quarter over quarter, ahead of Central at 9.1%. South and West were flat.</p>
            <svg viewBox="0 0 320 120" className={styles.previewChart} aria-hidden="true">
              {bars.map(([label, value], index) => (
                <g key={label} transform={`translate(${index * 80 + 12} 0)`}>
                  <rect x="10" y={100 - value} width="44" height={value} rx="3" />
                  <text x="32" y="114" textAnchor="middle">{label}</text>
                </g>
              ))}
            </svg>
            <span className={styles.previewBadge}>Verified · revenue by region · 48,120 rows</span>
          </div>
        </div>
        <div className={styles.previewCards}>
          <div><small>Trend</small><strong>+12.4%</strong><span>Monthly revenue, last 6 months</span></div>
          <div><small>Unusual value</small><strong>3 orders</strong><span>Refunds above the usual range in March</span></div>
          <div><small>Forecast</small><strong>₨ 4.1M</strong><span>Next month, ±6% measured error</span></div>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <div className={styles.site}>
      <header className={styles.nav}>
        <div className={styles.navInner}>
          <Link className={styles.brand} href="/" aria-label="Syntelio home"><span className={styles.mark} aria-hidden="true">S</span>Syntelio</Link>
          <nav aria-label="Site" className={styles.navLinks}>
            <a href="#product">Product</a><a href="#how">How it works</a><a href="#security">Security</a><a href="#faq">FAQ</a>
          </nav>
          <div className={styles.navActions}>
            <Link href="/login" className={styles.navLogin}>Log in</Link>
            <Link href="/signup" className={styles.buttonPrimary}>Create account</Link>
          </div>
        </div>
      </header>

      <main>
        <section className={styles.hero}>
          <div className={styles.heroText}>
            <p className={styles.kicker}>Synthesized Enterprise Intelligence</p>
            <h1>Answers from your business data, with the working shown.</h1>
            <p className={styles.heroLead}>
              Upload a spreadsheet or connect a database. Syntelio reads it, points out what matters and answers your questions in plain language.
              Every number is computed by a read-only engine and traceable to the rows behind it.
            </p>
            <div className={styles.heroActions}>
              <Link href="/signup" className={`${styles.buttonPrimary} ${styles.buttonLarge}`}>Create a free account</Link>
              <a href="#how" className={`${styles.buttonSecondary} ${styles.buttonLarge}`}>See how it works</a>
            </div>
            <p className={styles.heroNote}>Files up to 500 MB · 20+ formats · PostgreSQL, MySQL, SQL Server and Google Sheets</p>
          </div>
          <Preview />
        </section>

        <section className={styles.section} id="product">
          <div className={styles.sectionHead}>
            <h2>Everything between a raw file and a decision</h2>
            <p>Built for teams who need numbers they can defend, not just a chat window.</p>
          </div>
          <div className={styles.grid}>
            {features.map(([title, text]) => (
              <article key={title} className={styles.card}><h3>{title}</h3><p>{text}</p></article>
            ))}
          </div>
        </section>

        <section className={`${styles.section} ${styles.how}`} id="how">
          <div className={styles.sectionHead}>
            <h2>How it works</h2>
            <p>Four steps from file to verified answer. No modelling, no SQL, no setup project.</p>
          </div>
          <ol className={styles.steps}>
            {steps.map(([title, text], index) => (
              <li key={title}><span>{index + 1}</span><div><h3>{title}</h3><p>{text}</p></div></li>
            ))}
          </ol>
        </section>

        <section className={styles.section} id="security">
          <div className={styles.trust}>
            <div className={styles.sectionHead}>
              <h2>Built for trust</h2>
              <p>Language models are good at understanding a question and poor at arithmetic. Syntelio keeps them apart.</p>
            </div>
            <ul className={styles.trustList}>
              <li><h3>Numbers from a read-only engine</h3><p>Every figure comes from a validated query executed against your data. The model never supplies or rounds a number.</p></li>
              <li><h3>Lineage on every answer</h3><p>Each answer carries the dataset version, operation, filters and row count, so a result can be replayed and checked months later.</p></li>
              <li><h3>Your data stays in your workspace</h3><p>Workspaces are isolated. Roles decide who can see which datasets, and the audit history records every question, export and change.</p></li>
            </ul>
          </div>
        </section>

        <section className={styles.section} id="faq">
          <div className={styles.sectionHead}><h2>Questions, answered</h2></div>
          <div className={styles.faq}>
            {faq.map(([question, answer]) => (
              <details key={question}><summary>{question}</summary><p>{answer}</p></details>
            ))}
          </div>
        </section>

        <section className={styles.cta}>
          <h2>Start with the file you already have.</h2>
          <p>Create an account, upload a spreadsheet and read your first overview in a few minutes.</p>
          <Link href="/signup" className={`${styles.buttonPrimary} ${styles.buttonLarge}`}>Create a free account</Link>
        </section>
      </main>

      <footer className={styles.footer}>
        <span>© {new Date().getFullYear()} Syntelio · Synthesized Enterprise Intelligence</span>
        <nav aria-label="Footer"><Link href="/login">Log in</Link><Link href="/signup">Create account</Link><a href="#security">Security &amp; privacy</a></nav>
      </footer>
    </div>
  );
}
