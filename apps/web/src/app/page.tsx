/* Use case: Provides the initial product-facing web route.
What it does: Communicates the verified analytics workflow and current engineering phase without implying unfinished features exist. */

import Link from "next/link";

const foundations = [
  "Workspace-first isolation",
  "Database-executed numbers",
  "Calculation lineage",
  "Replaceable AI providers",
];

const upcoming = [
  "Evaluate retrieval against representative documents",
  "Compare model quality, privacy, latency and cost",
  "Verify production search backup and recovery",
];

export default function Home() {
  return (
    <main>
      <nav aria-label="Primary navigation">
        <a className="brand" href="#top" aria-label="ExecPlus home">
          <span className="brandMark" aria-hidden="true">E+</span>
          <span>ExecPlus</span>
        </a>
        <span className="phaseBadge">Phase 3 · In progress</span>
      </nav>

      <section className="hero" id="top">
        <div className="eyebrow">Operational clarity, backed by evidence</div>
        <h1>Ask your business data.<br />Trust the answer.</h1>
        <p className="heroCopy">
          ExecPlus is being built to turn structured datasets into clear answers,
          explainable charts, and decisions you can verify.
        </p>
        <p>Secure uploads, profiles, verified dashboards, saved analyses and workspace sharing are available locally. Explore profile observations and reference documents in the workspace.</p>
        <div className="heroActions">
          <a className="primaryAction" href="#architecture">Explore the foundation</a>
          <Link href="/workspace">Open your workspace →</Link>
        </div>
      </section>

      <section className="principles" aria-label="Product principles">
        {foundations.map((foundation, index) => (
          <article key={foundation}>
            <span>0{index + 1}</span>
            <h2>{foundation}</h2>
          </article>
        ))}
      </section>

      <section className="architecture" id="architecture">
        <div>
          <div className="eyebrow">Built for measured scale</div>
          <h2>A clean boundary between language and truth.</h2>
          <p>
            The analytics workflow uses configured models to interpret intent and explain results. A controlled query engine
            computes every number. Each response carries the dataset, operation,
            filters, and record count needed to trace it.
          </p>
        </div>
        <div className="flow" aria-label="ExecPlus request flow">
          <div><span>01</span><strong>Question</strong><small>Plain language</small></div>
          <div><span>02</span><strong>Validate</strong><small>Intent and access</small></div>
          <div><span>03</span><strong>Compute</strong><small>Read-only engine</small></div>
          <div><span>04</span><strong>Explain</strong><small>Answer and lineage</small></div>
        </div>
      </section>

      <section className="next">
        <div>
          <div className="eyebrow">Remaining evaluation gates</div>
          <h2>Proactive insights and hybrid knowledge</h2>
        </div>
        <ol>
          {upcoming.map((item) => <li key={item}>{item}</li>)}
        </ol>
      </section>

      <footer>
        <span>ExecPlus</span>
        <span>Exact computation · Explainable results</span>
      </footer>
    </main>
  );
}

