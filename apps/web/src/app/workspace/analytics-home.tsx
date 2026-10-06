/* Use case: Provides an ask-first analytics home using authorized source metadata.
What it does: Starts real conversations and opens saved work without inventing recency, KPIs or data. */

import { useEffect, useState } from "react";
import { Icon } from "./explore-components";
import type { ApiRequest } from "./profile-panel";

type SavedItem = { id: string; name: string; kind: string; shared: boolean };

export function AnalyticsHome({
  root, filename, request, onAsk, onSaved, onNavigate,
}: {
  root: string;
  filename: string;
  request: ApiRequest;
  onAsk: (question: string) => void;
  onSaved: (id: string) => void;
  onNavigate: (section: string) => void;
}) {
  const [question, setQuestion] = useState("");
  const [items, setItems] = useState<SavedItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let controller: AbortController;
    function refresh() {
      controller?.abort();
      controller = new AbortController();
      const signal = controller.signal;
      request<SavedItem[]>(`${root}/saved-items`, { signal })
      .then((value) => {
        if (!signal.aborted) { setItems(value); setError(""); setLoading(false); }
      })
      .catch((cause) => {
        if (!signal.aborted) {
          setItems([]);
          setError(cause instanceof Error ? cause.message : "Saved work is unavailable.");
          setLoading(false);
        }
      });
    }
    refresh();
    window.addEventListener("execplus-saved", refresh);
    return () => {
      controller.abort();
      window.removeEventListener("execplus-saved", refresh);
    };
  }, [root, request]);
  return (
    <section className="analyticsHome" aria-label="Analytics home">
      <div className="homeWelcome">
        <span className="homeAssistantMark"><Icon name="sparkle" size={26} /></span>
        <h2>Your questions. A clearer picture.</h2>
        <p>Meet your data partner. Explore an idea, find a pattern, or follow the evidence.</p>
      </div>
      <form className="homeComposer" onSubmit={(event) => {
        event.preventDefault();
        if (question.trim()) { onAsk(question.trim()); setQuestion(""); }
      }}>
        <label className="srOnly" htmlFor="home-question">Ask about your data</label>
        <input id="home-question" value={question} onChange={(event) => setQuestion(event.target.value)}
          placeholder="What would you like to know about your data?" maxLength={500} required />
        <div className="homeComposerFooter">
          <span className="homeSourcePill" title={filename}><Icon name="data" size={15} />{filename}</span>
          <button className="homeSourceChange" type="button" onClick={() => onNavigate("data")}>Change data</button>
          <button type="submit" aria-label="Explore this question" disabled={!question.trim()}><Icon name="arrow" size={19} /></button>
        </div>
      </form>
      <div className="homeQuickQuestions" aria-label="Start exploring">
        {[
          ["Help me understand my data", "Understand this data"],
          ["Show the first 10 records", "Explore records"],
        ].map(([question, label]) => <button key={question} type="button" onClick={() => onAsk(question)}>
          <Icon name="sparkle" size={14} />{label}
        </button>)}
        <button type="button" onClick={() => onNavigate("forecasts")}><Icon name="forecasts" size={14} />Explore forecasts</button>
      </div>
      <div className="homeLibraryGrid">
        <section className="homeLibraryCard" aria-label="Saved for this data">
          <header><h3>Saved for this data</h3><button type="button" onClick={() => onNavigate("saved")}>View all <Icon name="arrow" size={14} /></button></header>
          {loading ? <p role="status">Loading your saved work…</p> : error ? <p role="alert">{error}</p> : items.length ?
            <ul>{items.slice(0, 4).map((item) => <li key={item.id}><button type="button" onClick={() => onSaved(item.id)}>
              <span className="homeItemIcon"><Icon name={item.kind === "question" ? "chat" : "overview"} size={18} /></span>
              <span><strong>{item.name}</strong><small>{item.kind.replaceAll("_", " ")} · {item.shared ? "Workspace" : "Private"}</small></span>
              <Icon name="arrow" size={15} />
            </button></li>)}</ul> : <div className="homeLibraryEmpty"><Icon name="saved" size={22} /><p>Your next useful answer belongs here.</p><span>Save a question or calculated result to revisit it.</span></div>}
        </section>
        <section className="homeLibraryCard" aria-label="Explore your workspace">
          <header><h3>Keep exploring</h3><span className="homePrivateLabel">Your workspace</span></header>
          <ul>{[
            ["studies", "Studies & dashboards", "Build a board from saved, source-backed studies."],
            ["search", "Search data", "Filter your source and explore calculated charts."],
            ["refresh", "Refresh & alerts", "Review source updates and watch your metrics."],
          ].map(([id, name, description]) => <li key={id}><button type="button" onClick={() => onNavigate(id)}>
            <span className="homeItemIcon"><Icon name={id === "search" ? "data" : id} size={18} /></span>
            <span><strong>{name}</strong><small>{description}</small></span><Icon name="arrow" size={15} />
          </button></li>)}</ul>
        </section>
      </div>
    </section>
  );
}
