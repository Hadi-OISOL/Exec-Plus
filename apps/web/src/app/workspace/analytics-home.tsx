/* Use case: Provides an ask-first analytics home using authorized source metadata.
What it does: Starts real conversations and opens saved work without inventing recency, KPIs or data. */

import { useEffect, useState } from "react";
import { Icon } from "./explore-components";
import type { ApiRequest } from "./profile-panel";
import { GroupRelationshipForm } from "./group-relationship-form";
import { AgentSetup } from "./agent-setup";

type SavedItem = { id: string; name: string; kind: string; shared: boolean };
type DataContext = {
  state: string;
  definition: { description: string; columns: { name: string; role: string; unit: string; currency: string; unit_column: string }[] };
  column_types: Record<string, string>;
  preference: { goal: string };
};

export function AnalyticsHome({
  root, filename, request, onAsk, onSaved, onNavigate, onReview,
}: {
  root: string;
  filename: string;
  request: ApiRequest;
  onAsk: (question: string) => void;
  onSaved: (id: string) => void;
  onNavigate: (section: string) => void;
  onReview: () => void;
}) {
  const [question, setQuestion] = useState("");
  const [items, setItems] = useState<SavedItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [context, setContext] = useState<{ root: string; value: DataContext } | null>(null);
  const [contextError, setContextError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    request<DataContext>(`${root}/understanding`, { signal: controller.signal })
      .then(value => {
        if (!controller.signal.aborted) {
          setContext({ root, value });
          setContextError("");
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setContext(null);
          setContextError("Your saved data context could not be loaded. Open Review & refine data understanding to try again.");
        }
      });
    return () => controller.abort();
  }, [root, request]);
  const meaning = context?.root === root ? context.value : null;
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
      <AgentSetup workspaceId={root.split("/")[2]} request={request} onEdit={() => onNavigate("memory")} />
      <div className="studioHomeTop">
      <div className="studioQuestionSpace">
      <div className="homeWelcome">
        <span className="studioEyebrow"><Icon name="sparkle" size={16} /> YOUR ANALYSIS STUDIO</span>
        <h2>What would you like to explore?</h2>
        <p>Ask a follow-up or choose a suggested question.</p>
      </div>
      <form className="homeComposer" onSubmit={(event) => {
        event.preventDefault();
        if (question.trim()) { onAsk(question.trim()); setQuestion(""); }
      }}>
        <label className="srOnly" htmlFor="home-question">Ask about your data</label>
        <textarea id="home-question" rows={2} value={question} onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (question.trim()) { onAsk(question.trim()); setQuestion(""); } } }}
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
          ["Find patterns in my data", "Find patterns"],
          ["Show the first 10 records", "Explore records"],
          ["Show a diagram of my data", "Map this file"],
        ].map(([question, label]) => <button key={question} type="button" onClick={() => onAsk(question)}>
          <Icon name="sparkle" size={14} />{label}
        </button>)}
        <button type="button" onClick={() => onNavigate("forecasts")}><Icon name="forecasts" size={14} />Explore forecasts</button>
      </div>
      </div>
      <aside className="studioSourceSpace" aria-label="Source context">
      {meaning ?
        <section className="homeDataContext" aria-label="Saved context for this data">
          <header>
            <span className="studioSourceIcon"><Icon name="data" size={22} /></span>
            <div><span className="homeContextEyebrow">WORKING WITH</span><h3>{filename}</h3></div>
          </header>
          <span className="homeContextStatus" data-confirmed={meaning.state === "confirmed"}><Icon name={meaning.state === "confirmed" ? "check" : "prepare"} size={13} />{meaning.state === "confirmed" ? "Definitions confirmed" : "Definitions need review"}</span>
          {meaning.definition.description && <p className="homeContextDescription">{meaning.definition.description}</p>}
          {meaning.state !== "confirmed" && <p className="homeContextNotice">This saved description is a draft. Review it before relying on it.</p>}
          {meaning.preference.goal && <div className="homeContextGoal"><span>Your goal · Private</span><p>{meaning.preference.goal}</p></div>}
          <div className="homeContextActions">
            <button type="button" onClick={() => onAsk("Help me understand my data")}>Explain this data <Icon name="arrow" size={14} /></button>
            {meaning.preference.goal && <button type="button" onClick={() => onAsk("Analyze my data")}>Explore my goal</button>}
            <button type="button" onClick={onReview}>Review saved details</button>
          </div>
        </section> : <div className="homeDataContext"><span className="homeContextEyebrow">WORKING WITH</span><h3>{filename}</h3><p className="homeContextNotice" role="status">{contextError || "Loading your saved data context…"}</p></div>}
      <button className="studioMemoryShortcut" type="button" onClick={() => onNavigate("memory")}><Icon name="memory" size={18} /><span><strong>Make it your data partner</strong><small>Set what ExecPlus remembers about you</small></span><Icon name="arrow" size={16} /></button>
      </aside>
      </div>
      <details className="homeMoreTools"><summary>Explore tools & saved work</summary>
      <section className="studioToolSection" aria-label="Analysis tools">
        <header className="studioSectionHeading"><div><span className="studioEyebrow">A GOOD PLACE TO START</span><h3>Choose a direction</h3></div><p>Real tools. Answers you can inspect.</p></header>
        <div className="studioToolGrid">
          {[
            { icon: "patterns", title: "Find the connections", description: "Explore relationships and differences in your data.", action: () => onAsk("Find patterns in my data"), label: "Find patterns in this data" },
            { icon: "forecasts", title: "Look ahead", description: "Forecast over time or try an explicit what-if.", action: () => onNavigate("forecasts"), label: "Open forecasts and what-ifs" },
            { icon: "decisions", title: "Plan your next move", description: "Find unusual values and compare resource choices.", action: () => onNavigate("decisions"), label: "Open anomalies and decisions" },
          ].map(tool => <button className="studioToolCard" key={tool.title} type="button" aria-label={tool.label} onClick={tool.action}><span className="studioToolIcon"><Icon name={tool.icon} size={23} /></span><strong>{tool.title}</strong><span>{tool.description}</span><Icon name="arrow" size={17} /></button>)}
        </div>
        {meaning && <GroupRelationshipForm key={root} understanding={meaning} onAsk={onAsk} onReview={onReview} />}
      </section>
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
      </details>
    </section>
  );
}
