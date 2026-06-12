"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Bot,
  Clock3,
  Compass,
  Database,
  Home,
  Loader2,
  MapPinned,
  MessageCircle,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  User
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type View = "chat" | "explore" | "history";

type ChatResult = {
  intent: string;
  mode: string;
  answer: string;
  translation?: {
    translation?: string;
    breakdown?: Array<{ dialect: string; bm: string; contoh?: string }>;
    confidence_label?: string;
  };
  kelantan?: {
    summary?: string;
    response_type?: string;
    items?: Array<{
      name: string;
      district?: string;
      category?: string;
      description: string;
      confidence?: number;
    }>;
    used_llm?: boolean;
  };
  eval?: Record<string, number | string>;
  answer_type?: string;
  route?: { mode?: string; intent?: string };
  contexts?: Array<{
    score: number;
    collection: string;
    category: string;
    title: string;
    text: string;
  }>;
};

type Message = {
  id: number;
  role: "assistant" | "user";
  content: string;
  result?: ChatResult;
};

type HistoryItem = {
  id: number;
  prompt: string;
  answer: string;
  mode: string;
  intent: string;
  time: string;
};

type Metrics = {
  documents: number;
  model: string;
  dataset: string;
  collections: string[];
};

type CatalogItem = {
  id: string;
  name: string;
  collection: "tourism" | "food" | "culture";
  category: string;
  district?: string;
  description: string;
  prompt: string;
  image_keyword: string;
};

type NavView = View | "landing";

const navItems: Array<{ id: NavView; label: string; icon: typeof MessageCircle }> = [
  { id: "landing", label: "Home", icon: Home },
  { id: "chat", label: "Chat", icon: MessageCircle },
  { id: "explore", label: "Pelancongan", icon: Compass },
  { id: "history", label: "History", icon: Clock3 }
];

const prompts = [
  "Mu nok gi mano",
  "Cadangan makanan tradisional Kelantan",
  "Tempat menarik di Kota Bharu",
  "Apa budaya terkenal di Kelantan?"
];

const catalogFilters = [
  { label: "Semua", value: "all" },
  { label: "Tempat Menarik", value: "tourism" },
  { label: "Makanan Tradisional", value: "food" },
  { label: "Budaya", value: "culture" }
];

function shortMetric(value: number | string | undefined) {
  return typeof value === "number" ? value.toFixed(2) : value || "-";
}

function renderAnswer(result: ChatResult) {
  if (result.intent === "translation" && result.translation) {
    const breakdown = result.translation.breakdown || [];
    return (
      <div className="answer">
        <span className="answer-kicker">Terjemahan</span>
        <p className="translation-line">{result.translation.translation}</p>
        {breakdown.length ? (
          <div className="token-grid">
            {breakdown.map((item, index) => (
              <span key={`${item.dialect}-${index}`}>
                <b>{item.dialect}</b>
                {item.bm}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  const items = result.kelantan?.items || [];
  if (items.length) {
    return (
      <div className="answer">
        <p>{result.kelantan?.summary}</p>
        <div className="answer-results">
          {items.map((item) => (
            <article key={item.name}>
              <div>
                <b>{item.name}</b>
                <span>{item.category || item.district || "Kelantan"}</span>
              </div>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
      </div>
    );
  }

  return <p>{result.answer}</p>;
}

export default function HomePage() {
  const [view, setView] = useState<NavView>("landing");
  const [mode, setMode] = useState("Auto");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [catalogFilter, setCatalogFilter] = useState("all");
  const [catalogImages, setCatalogImages] = useState<Record<string, string>>({});
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      role: "assistant",
      content: "Assalamualaikum. Saya JomKecek, pembantu untuk dialek, makanan, budaya dan pelancongan Kelantan."
    }
  ]);

  const lastResult = useMemo(
    () => [...messages].reverse().find((message) => message.result)?.result,
    [messages]
  );

  useEffect(() => {
    fetch(`${API_BASE}/metrics`)
      .then((response) => response.json())
      .then(setMetrics)
      .catch(() => setMetrics(null));
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/catalog`)
      .then((response) => response.json())
      .then((data) => setCatalog(data.items || []))
      .catch(() => setCatalog([]));
  }, []);

  useEffect(() => {
    const saved = window.localStorage.getItem("jomkecek-history");
    if (saved) setHistory(JSON.parse(saved));
  }, []);

  useEffect(() => {
    window.localStorage.setItem("jomkecek-history", JSON.stringify(history.slice(0, 30)));
  }, [history]);

  const filteredCatalog = useMemo(
    () => catalog.filter((item) => catalogFilter === "all" || item.collection === catalogFilter),
    [catalog, catalogFilter]
  );

  useEffect(() => {
    const missing = filteredCatalog
      .filter((item) => !(item.id in catalogImages))
      .slice(0, 12);
    if (!missing.length) return;

    let cancelled = false;
    Promise.all(
      missing.map((item) =>
        fetch(`${API_BASE}/images`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keywords: [item.image_keyword], limit_per_keyword: 1 })
        })
          .then((response) => response.json())
          .then((data) => [item.id, data.images?.[0]?.url || ""] as const)
          .catch(() => [item.id, ""] as const)
      )
    ).then((pairs) => {
      if (cancelled) return;
      setCatalogImages((current) => {
        const next = { ...current };
        for (const [id, url] of pairs) {
          next[id] = url;
        }
        return next;
      });
    });

    return () => {
      cancelled = true;
    };
  }, [filteredCatalog, catalogImages]);

  async function submitPrompt(prompt: string, nextMode = mode) {
    const cleanPrompt = prompt.trim();
    if (!cleanPrompt || loading) return;

    setView("chat");
    setMessages((current) => [...current, { id: Date.now(), role: "user", content: cleanPrompt }]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: cleanPrompt, mode: nextMode })
      });

      if (!response.ok) throw new Error("Chat request failed");
      const result: ChatResult = await response.json();

      setMessages((current) => [
        ...current,
        { id: Date.now() + 1, role: "assistant", content: result.answer, result }
      ]);
      setHistory((current) => [
        {
          id: Date.now(),
          prompt: cleanPrompt,
          answer: result.answer,
          mode: result.mode || nextMode,
          intent: result.intent || "-",
          time: new Date().toLocaleString("ms-MY")
        },
        ...current
      ]);
    } catch {
      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: "Maaf, pelayan API tidak dapat dihubungi. Pastikan FastAPI sedang berjalan."
        }
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitPrompt(input);
  }

  return (
    <main className="jk-shell">
      <aside className="jk-sidebar">
        <div className="brand">
          <img src={`${API_BASE}/assets/kijang_bukamata.png`} alt="" />
          <div>
            <strong>JomKecek</strong>
            <span>Kelantan AI Guide</span>
          </div>
        </div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button className={view === item.id ? "active" : ""} key={item.id} type="button" onClick={() => setView(item.id)}>
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>
        <section className="system-card">
          <span>Dataset</span>
          <strong>{metrics?.documents ?? "-"}</strong>
          <p>{metrics?.dataset || "DATA_JOMKECEK_CLEANED"}</p>
        </section>
      </aside>

      <section className="jk-main">
        <header className="topline">
          <div>
            <span className="eyebrow">Controlled Hybrid Chatbot</span>
            <h1>{view === "landing" ? "JomKecek untuk demo akademik." : view === "chat" ? "Kecek molek, jawab berpandu." : view === "explore" ? "Pelancongan Kelantan" : "Sejarah Perbualan"}</h1>
          </div>
        </header>

        {view === "landing" ? (
          <section className="landing-view">
            <article className="landing-hero">
              <div>
                <span className="eyebrow">FYP Safe Demo</span>
                <h2>Dialek, budaya, makanan dan pelancongan Kelantan dalam satu chatbot terkawal.</h2>
                <p>
                  JomKecek direka untuk presentation FYP tanpa akaun pengguna sebenar. Tiada emel, nombor telefon atau kata laluan dikumpul.
                  Sejarah chat hanya disimpan di browser untuk demo.
                </p>
                <div className="landing-actions">
                  <button type="button" onClick={() => setView("chat")}>
                    <MessageCircle size={18} />
                    Mula Chat Demo
                  </button>
                  <button type="button" onClick={() => setView("explore")}>
                    <Compass size={18} />
                    Lihat Kandungan
                  </button>
                </div>
              </div>
              <img src={`${API_BASE}/assets/kijang_bukamata.png`} alt="JomKecek mascot" />
            </article>

            <div className="landing-grid">
              <article>
                <ShieldCheck size={22} />
                <h3>Privacy-safe</h3>
                <p>Tiada login sebenar dan tiada simpanan data peribadi di server.</p>
              </article>
              <article>
                <Database size={22} />
                <h3>Dataset berpandu</h3>
                <p>{metrics?.documents ?? "-"} rekod digunakan untuk dialek, makanan, budaya dan tourism.</p>
              </article>
              <article>
                <BarChart3 size={22} />
                <h3>Evaluation ready</h3>
                <p>Jawapan chat masih paparkan metrik seperti faithfulness dan context precision.</p>
              </article>
            </div>
          </section>
        ) : null}

        {view === "chat" ? (
          <div className="chat-workspace">
            <section className="chat-panel">
              <div className="prompt-row">
                {prompts.map((prompt) => (
                  <button key={prompt} type="button" onClick={() => submitPrompt(prompt)}>
                    <Sparkles size={15} />
                    {prompt}
                  </button>
                ))}
              </div>
              <div className="messages">
                {messages.map((message) => (
                  <article className={`message ${message.role}`} key={message.id}>
                    <span className="avatar">{message.role === "assistant" ? <Bot size={18} /> : <User size={18} />}</span>
                    <div className="bubble">{message.result ? renderAnswer(message.result) : message.content}</div>
                  </article>
                ))}
                {loading ? (
                  <article className="message assistant">
                    <span className="avatar"><Bot size={18} /></span>
                    <div className="bubble typing"><Loader2 size={16} /> Menyemak pangkalan data...</div>
                  </article>
                ) : null}
              </div>
              <form className="composer" onSubmit={onSubmit}>
                <Search size={18} />
                <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Taip ayat dialek atau soalan tentang Kelantan..." />
                <button disabled={loading || !input.trim()} type="submit" aria-label="Hantar">
                  <Send size={18} />
                </button>
              </form>
            </section>

            <aside className="insight-panel">
              <section>
                <h2><ShieldCheck size={18} /> Guardrails</h2>
                <p>Jawapan dikawal kepada domain Kelantan dan konteks dataset.</p>
                {lastResult?.route?.mode && (
                  <p style={{ fontSize: "0.72rem", marginTop: "0.4rem", opacity: 0.7 }}>
                    Mode: <strong>{lastResult.route.mode}</strong>
                    {lastResult.answer_type ? ` · ${lastResult.answer_type}` : ""}
                  </p>
                )}
              </section>
              <section>
                <h2><BarChart3 size={18} /> Evaluasi Automatik</h2>
                <dl>
                  <dt>ROUGE-L</dt><dd>{shortMetric(lastResult?.eval?.rouge_l)}</dd>
                  <dt>Faithfulness</dt><dd>{shortMetric(lastResult?.eval?.faithfulness)}</dd>
                  <dt>Context</dt><dd>{shortMetric(lastResult?.eval?.context_precision)}</dd>
                </dl>
              </section>
              {(lastResult?.eval?.judge_faithfulness !== undefined) && (
                <section>
                  <h2><Bot size={18} /> LLM Judge (3b)</h2>
                  <dl>
                    <dt>Faithfulness</dt><dd>{shortMetric(lastResult?.eval?.judge_faithfulness)}</dd>
                    <dt>Relevancy</dt><dd>{shortMetric(lastResult?.eval?.judge_relevancy)}</dd>
                    <dt>Completeness</dt><dd>{shortMetric(lastResult?.eval?.judge_completeness)}</dd>
                  </dl>
                </section>
              )}
              <section>
                <h2><Database size={18} /> Collections</h2>
                <p>{metrics?.collections?.join(", ") || "dialect, tourism, food, culture"}</p>
              </section>
            </aside>
          </div>
        ) : null}

        {view === "explore" ? (
          <>
            <div className="catalog-toolbar">
              <p>
                Senarai ini dibaca terus daripada dataset bagi kategori tempat menarik,
                makanan tradisional dan budaya.
              </p>
              <div>
                {catalogFilters.map((filter) => (
                  <button
                    className={catalogFilter === filter.value ? "active" : ""}
                    key={filter.value}
                    type="button"
                    onClick={() => setCatalogFilter(filter.value)}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>
            </div>
            <section className="explore-view">
              {filteredCatalog.map((item) => (
                <article className="explore-item" key={item.id}>
                  <div className="catalog-image">
                    {catalogImages[item.id] ? <img src={catalogImages[item.id]} alt={item.name} /> : <span>{item.category}</span>}
                  </div>
                  <span>{item.category}{item.district ? ` / ${item.district}` : ""}</span>
                  <h2>{item.name}</h2>
                  <p>{item.description}</p>
                  <button type="button" onClick={() => submitPrompt(item.prompt, "Info Kelantan")}>
                    <MapPinned size={16} />
                    Tanya JomKecek
                  </button>
                </article>
              ))}
            </section>
          </>
        ) : null}

        {view === "history" ? (
          <section className="history-view">
            {history.length ? history.map((item) => (
              <article key={item.id}>
                <div>
                  <span>{item.time}</span>
                  <h2>{item.prompt}</h2>
                  <p>{item.answer}</p>
                </div>
                <button type="button" onClick={() => submitPrompt(item.prompt, item.mode)}>
                  <RotateCcw size={16} />
                  Tanya semula
                </button>
              </article>
            )) : (
              <div className="empty">
                <Clock3 size={28} />
                <p>Belum ada sejarah. Mulakan soalan pertama di Chat.</p>
              </div>
            )}
          </section>
        ) : null}

      </section>
    </main>
  );
}
