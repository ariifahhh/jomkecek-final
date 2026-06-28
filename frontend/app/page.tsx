"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  Bot,
  Check,
  ChevronDown,
  ChevronUp,
  Clock3,
  Compass,
  Copy,
  Database,
  Home,
  Lightbulb,
  Loader2,
  MapPinned,
  MessageCircle,
  Moon,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Sun,
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
    breakdown?: Array<{ dialect: string; bm: string; contoh?: string; contoh_bm?: string; matched?: boolean; confidence?: number; approximated?: boolean }>;
    confidence_label?: string;
    direction?: "dialect_to_bm" | "bm_to_dialect";
    rag_examples?: Array<{ dialek: string; bm: string }>;
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
  { id: "landing", label: "Laman Utama", icon: Home },
  { id: "chat", label: "Chat", icon: MessageCircle },
  { id: "explore", label: "Pelancongan", icon: Compass },
  { id: "history", label: "Sejarah", icon: Clock3 }
];

const dialectPrompts = [
  "Saya nak awak tunjuk jalan ke pantai.",
  "Di mana saya boleh beli cenderamata?",
  "Saya hendak pergi ke pasar malam.",
  "Sayo nok awok tunjuk jale gi pata.",
  "Kat mano kawe buleh beli hadioh ole-ole?",
  "Kawe nok gi pasa male.",
];

const kelantanPrompts = [
  "Cadangan makanan tradisional Kelantan",
  "Tempat menarik di Kota Bharu",
  "Apa budaya terkenal di Kelantan?",
  "Ceritakan tentang Wayang Kulit Kelantan",
  "Apa gelaran negeri Kelantan?",
];

const catalogFilters = [
  { label: "Semua", value: "all" },
  { label: "Tempat Menarik", value: "tourism" },
  { label: "Makanan Tradisional", value: "food" },
  { label: "Budaya", value: "culture" }
];

const ITEMS_PER_PAGE = 12;

function MetricBar({ label, value }: { label: string; value: number | string | undefined }) {
  if (typeof value !== "number") {
    return (
      <div className="metric-bar-row">
        <span className="metric-label">{label}</span>
        <div className="metric-bar-track" />
        <span className="metric-val muted">–</span>
      </div>
    );
  }
  const pct = Math.min(Math.max(value, 0), 1) * 100;
  const cls = pct >= 60 ? "good" : pct >= 30 ? "mid" : "low";
  return (
    <div className="metric-bar-row">
      <span className="metric-label">{label}</span>
      <div className="metric-bar-track">
        <div className={`metric-bar-fill ${cls}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="metric-val">{value.toFixed(2)}</span>
    </div>
  );
}

function highlightWords(text: string, words: string[]): React.ReactNode {
  if (!words.length || !text) return text;
  const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`(${escaped.join("|")})`, "gi");
  const parts = text.split(pattern);
  return parts.map((part, i) =>
    words.some((w) => w.toLowerCase() === part.toLowerCase()) ? (
      <strong key={i} className="highlight-word">{part}</strong>
    ) : (
      part
    )
  );
}

function renderAnswer(result: ChatResult) {
  if (result.intent === "translation" && result.translation) {
    const breakdown = result.translation.breakdown || [];
    const ragExamples = result.translation.rag_examples || [];
    const isToBm = result.translation.direction === "dialect_to_bm";
    const fromLabel = isToBm ? "Dialek Kelantan" : "BM Standard";
    const toLabel = isToBm ? "BM Standard" : "Dialek Kelantan";
    // Words to highlight in example sentences — the dialect tokens from the user's input
    const dialectWords = breakdown.map((item) => item.dialect).filter(Boolean);

    return (
      <div className="answer">
        <div className="translation-direction">
          <span className={`lang-badge ${isToBm ? "badge-dialect" : "badge-bm"}`}>{fromLabel}</span>
          <span className="direction-arrow">→</span>
          <span className={`lang-badge ${isToBm ? "badge-bm" : "badge-dialect"}`}>{toLabel}</span>
        </div>
        <p className="translation-line">{result.translation.translation}</p>
        {breakdown.length ? (
          <div className="token-grid">
            {breakdown.map((item, index) => (
              <div
                className={`token-card${item.approximated ? " token-approx" : ""}${item.confidence === 0 ? " token-unknown" : ""}`}
                key={`${item.dialect}-${index}`}
              >
                <div className="token-from">
                  <span className="token-lang-label">{isToBm ? "Dialek" : "BM"}</span>
                  <b>{item.dialect}</b>
                </div>
                <div className="token-to">
                  <span className="token-lang-label">{isToBm ? "BM" : "Dialek"}</span>
                  <span className="token-bm">{item.bm}</span>
                  {item.approximated && <span className="token-approx-badge">~akhiran</span>}
                </div>
                {item.contoh && <span className="token-example">{item.contoh}</span>}
              </div>
            ))}
          </div>
        ) : null}
        {ragExamples.length > 0 && (
          <div className="rag-examples">
            <span className="answer-kicker-sm">Contoh Ayat dari Dataset</span>
            {ragExamples.map((ex, i) => (
              <div className="rag-example-row" key={i}>
                <span className="rag-dialect">{highlightWords(ex.dialek, dialectWords)}</span>
                {ex.bm && <span className="rag-bm">{ex.bm}</span>}
              </div>
            ))}
          </div>
        )}
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

const bakuExamples = [
  { from: "nk g", to: "NAK PERGI" },
  { from: "xde", to: "TIADA" },
  { from: "dh mkn", to: "SUDAH MAKAN" },
  { from: "sbb ape", to: "SEBAB APA" },
];

const imbuhanExamples = [
  { from: "diambil", to: "DI AMBIL" },
  { from: "berjalan", to: "BER JALAN" },
  { from: "macamtu", to: "MACAM TU" },
  { from: "takpayah", to: "TAK PAYAH" },
  { from: "gituah", to: "GITU LAH" },
];

function TipsTerjemahan() {
  const [open, setOpen] = useState(true);
  return (
    <div className="tips-panel">
      <div className="tips-header" onClick={() => setOpen((o) => !o)}>
        <div className="tips-header-left">
          <span className="tips-icon"><Lightbulb size={18} /></span>
          <div>
            <strong>TIPS TERJEMAHAN</strong>
            <p>Panduan untuk terjemahan yang lebih tepat.</p>
          </div>
        </div>
        <button className="tips-toggle" type="button" aria-label="Togol tips">
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>
      {open && (
        <div className="tips-body">
          <div className="tip-section">
            <h3><span className="tip-num tip-num-blue">01.</span> Bahasa Melayu Standard &amp; Ejaan Betul</h3>
            <p>Gunakan <strong>Bahasa Melayu standard</strong> dan pastikan ejaan betul supaya sistem dapat mengenal pasti maksud perkataan dengan lebih tepat. Elakkan singkatan atau bahasa sembang (Contoh):</p>
            <div className="tip-examples">
              {bakuExamples.map((ex) => (
                <div key={ex.from} className="tip-ex-card tip-ex-yellow">
                  <span className="tip-ex-from">{ex.from}</span>
                  <span className="tip-ex-to">{ex.to}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="tip-section">
            <h3><span className="tip-num tip-num-teal">02.</span> Pisahkan Perkataan (Imbuhan)</h3>
            <p>Gunakan <strong>jarak (space)</strong> antara perkataan atau imbuhan yang digabungkan bagi membantu sistem memahami struktur perkataan (Contoh):</p>
            <div className="tip-examples">
              {imbuhanExamples.map((ex) => (
                <div key={ex.from} className="tip-ex-card tip-ex-blue">
                  <span className="tip-ex-from">{ex.from}</span>
                  <span className="tip-ex-to">{ex.to}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="tip-section">
            <h3><span className="tip-num tip-num-blue">03.</span> Gunakan Ayat Lengkap</h3>
            <p>Gunakan ayat yang mempunyai <strong>konteks</strong> supaya sistem dapat memahami maksud sebenar sebelum menterjemahkan.</p>
            <div className="tip-examples">
              <div className="tip-ex-card tip-ex-yellow">
                <span className="tip-ex-from">❌ gi mano</span>
                <span className="tip-ex-to">KURANG KONTEKS</span>
              </div>
              <div className="tip-ex-card tip-ex-blue">
                <span className="tip-ex-from">✅ Awak pergi mana?</span>
                <span className="tip-ex-to">LEBIH TEPAT</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const tipsPelanconganItems = [
  {
    num: "01", color: "blue" as const,
    title: "Gunakan Nama Spesifik",
    body: <>Nyatakan nama <strong>tempat, makanan atau acara</strong> yang tepat untuk jawapan lebih terperinci. Contoh: <em>"Ceritakan tentang Pantai Cahaya Bulan"</em>.</>,
  },
  {
    num: "02", color: "teal" as const,
    title: "Tanya Fakta Kelantan",
    body: <>Gunakan soalan terus untuk mendapatkan maklumat ringkas dan tepat. Contoh: <em>"Apakah ibu negeri Kelantan?"</em></>,
  },
  {
    num: "03", color: "blue" as const,
    title: "Minta Cadangan",
    body: <>Gunakan perkataan seperti <strong>cadangan, senaraikan</strong> atau <strong>berikan</strong> untuk mendapatkan beberapa pilihan. Contoh: <em>"Senaraikan tempat menarik di Kota Bharu"</em>.</>,
  },
  {
    num: "04", color: "teal" as const,
    title: "Minta Penerangan",
    body: <>Gunakan perkataan seperti <strong>ceritakan, terangkan, huraikan</strong> atau <strong>bagaimana</strong> untuk mendapatkan penerangan lanjut. Contoh: <em>"Ceritakan tentang Wayang Kulit Kelantan"</em>.</>,
  },
];

const kawalanSkopItems = [
  {
    icon: "🗺️",
    title: "Terhad kepada Kelantan",
    body: "Sistem hanya menyediakan maklumat berkaitan Kelantan. Pertanyaan tentang negeri atau negara lain tidak akan dilayan.",
  },
  {
    icon: "📚",
    title: "Skop Maklumat",
    body: "JomKecek meliputi makanan tradisional, budaya dan warisan, tempat menarik serta fakta umum Kelantan.",
  },
  {
    icon: "💡",
    title: "Sumber Jawapan",
    body: "Maklumat daripada pangkalan data JomKecek digunakan apabila tersedia. Jika tiada, AI akan menjawab dengan memastikan kandungan kekal dalam skop Kelantan.",
  },
];

function TipsPelancongan() {
  const [open, setOpen] = useState(true);
  return (
    <div className="tips-panel">
      <div className="tips-header" onClick={() => setOpen((o) => !o)}>
        <div className="tips-header-left">
          <span className="tips-icon tips-icon-teal"><Compass size={18} /></span>
          <div>
            <strong>TIPS PERTANYAAN</strong>
            <p>Panduan untuk carian pelancongan yang lebih tepat.</p>
          </div>
        </div>
        <button className="tips-toggle" type="button" aria-label="Togol tips">
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>
      {open && (
        <div className="tips-body">
          {tipsPelanconganItems.map((item) => (
            <div key={item.num} className="tip-section">
              <h3>
                <span className={`tip-num tip-num-${item.color}`}>{item.num}.</span> {item.title}
              </h3>
              <p>{item.body}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function KawalanSkop() {
  const [open, setOpen] = useState(true);
  return (
    <div className="tips-panel">
      <div className="tips-header" onClick={() => setOpen((o) => !o)}>
        <div className="tips-header-left">
          <span className="tips-icon tips-icon-maroon"><ShieldCheck size={18} /></span>
          <div>
            <strong>KAWALAN SKOP</strong>
            <p>Had dan kawalan sistem pertanyaan.</p>
          </div>
        </div>
        <button className="tips-toggle" type="button" aria-label="Togol kawalan skop">
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>
      {open && (
        <div className="tips-body">
          {kawalanSkopItems.map((item) => (
            <div key={item.title} className="tip-section">
              <h3><span className="tip-scope-icon">{item.icon}</span> {item.title}</h3>
              <p>{item.body}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function HomePage() {
  const [view, setView] = useState<NavView>("landing");
  const [mode, setMode] = useState("Terjemahan Dialek");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [catalogFilter, setCatalogFilter] = useState("all");
  const [catalogImages, setCatalogImages] = useState<Record<string, string>>({});
  const [catalogPage, setCatalogPage] = useState(0);
  const [catalogSearch, setCatalogSearch] = useState("");
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
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

  const catalogStats = useMemo(() => ({
    tourism: catalog.filter((item) => item.collection === "tourism").length,
    food: catalog.filter((item) => item.collection === "food").length,
    culture: catalog.filter((item) => item.collection === "culture").length,
  }), [catalog]);

  const filteredCatalog = useMemo(() => {
    const rowOf = (id: string) => parseInt(id.split("-").pop() ?? "9999", 10);
    return catalog
      .filter((item) => {
        if (catalogFilter !== "all" && item.collection !== catalogFilter) return false;
        if (!catalogSearch) return true;
        const q = catalogSearch.toLowerCase();
        return item.name.toLowerCase().includes(q) || item.description.toLowerCase().includes(q);
      })
      .sort((a, b) => rowOf(a.id) - rowOf(b.id));
  }, [catalog, catalogFilter, catalogSearch]);

  const totalPages = Math.ceil(filteredCatalog.length / ITEMS_PER_PAGE);
  const pagedCatalog = useMemo(
    () => filteredCatalog.slice(catalogPage * ITEMS_PER_PAGE, (catalogPage + 1) * ITEMS_PER_PAGE),
    [filteredCatalog, catalogPage]
  );

  useEffect(() => {
    setCatalogPage(0);
  }, [catalogFilter, catalogSearch]);

  useEffect(() => {
    const onScroll = () => setShowScrollTop(window.scrollY > 480);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  useEffect(() => {
    const missing = pagedCatalog
      .filter((item) => !(item.id in catalogImages))
      .slice(0, 10);
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
  }, [pagedCatalog, catalogImages]);

  function copyToClipboard(id: number, text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    }).catch(() => {});
  }

  function showToast(message: string) {
    setToast(message);
    setTimeout(() => setToast(null), 3500);
  }

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
      showToast("Pelayan API tidak dapat dihubungi. Pastikan FastAPI sedang berjalan.");
      setMessages((current) => [
        ...current,
        { id: Date.now() + 1, role: "assistant", content: "Maaf, pelayan tidak dapat dihubungi." }
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
    <main className={`jk-shell${view === "chat" ? " chat-mode" : ""}`}>
      <aside className="jk-sidebar">
        <div className="brand">
          <img src="/kijang_bukamata.png" alt="" />
          <div>
            <strong>JomKecek</strong>
            <span>Panduan AI Kelantan</span>
          </div>
        </div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button className={view === item.id ? "active" : ""} key={item.id} type="button" onClick={() => { setView(item.id); if (item.id === "chat") setMode("Terjemahan Dialek"); }}>
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>
        <section className="system-card">
          <span>Set Data</span>
          <strong>{metrics?.documents ?? "-"}</strong>
          <p>{metrics?.dataset || "DATA_JOMKECEK_CLEANED"}</p>
        </section>
        <button
          className="sidebar-dark-toggle"
          type="button"
          aria-label="Togol mod gelap"
          onClick={() => setDarkMode((d) => !d)}
        >
          {darkMode ? <Sun size={15} /> : <Moon size={15} />}
          {darkMode ? "Mod Cerah" : "Mod Gelap"}
        </button>
      </aside>

      <section className="jk-main">
        <header className="topline">
          <div>
            <span className="eyebrow">JomKecek</span>
            <h1>{view === "landing" ? "Tentang JomKecek." : view === "chat" ? "Kecek molek, jawab berpandu." : view === "explore" ? "Pelancongan Kelantan" : "Rekod Perbualan"}</h1>
          </div>
        </header>

        {view === "landing" ? (
          <section className="landing-view">
            <article className="landing-hero">
              <div>
                <span className="eyebrow">Chatbot AI Kelantan</span>
                <h2>Dialek, budaya, makanan dan pelancongan Kelantan dalam satu platform.</h2>
                <p>
                  JomKecek ialah chatbot berasaskan kecerdasan buatan yang khusus untuk negeri Kelantan.
                  Tanya soalan dalam dialek Kelantan atau Bahasa Melayu standard — JomKecek faham kedua-duanya
                  dan menjawab berdasarkan pangkalan data tempatan yang disahkan.
                </p>
                <div className="landing-actions">
                  <button type="button" onClick={() => { setView("chat"); setMode("Terjemahan Dialek"); }}>
                    <MessageCircle size={18} />
                    Mula Chat
                  </button>
                  <button type="button" onClick={() => setView("explore")}>
                    <Compass size={18} />
                    Terokai Kandungan
                  </button>
                </div>
              </div>
              <img src="/kijang_bukamata.png" alt="JomKecek maskot" />
            </article>

            <div className="landing-grid">
              <article>
                <MessageCircle size={22} />
                <h3>Dialek Kelantan</h3>
                <p>Terjemahkan perkataan dan ayat dialek Kelantan ke Bahasa Melayu standard — dan sebaliknya — dengan pecahan makna setiap perkataan.</p>
              </article>
              <article>
                <Database size={22} />
                <h3>Pangkalan Data Tempatan</h3>
                <p>{metrics?.documents ?? "-"} rekod merangkumi tempat menarik, makanan tradisional, budaya dan dialek Kelantan yang telah disahkan.</p>
              </article>
              <article>
                <ShieldCheck size={22} />
                <h3>Jawapan Berpandu Konteks</h3>
                <p>Sistem RAG hibrid memastikan setiap jawapan bersumberkan data tempatan yang relevan, bukan tekaan semata-mata.</p>
              </article>
            </div>
          </section>
        ) : null}

        {view === "chat" ? (
          <>
            <div className="chat-mode-switch">
              <div className="chat-mode-switch-inner">
                <button
                  className={mode === "Terjemahan Dialek" ? "active" : ""}
                  type="button"
                  onClick={() => setMode("Terjemahan Dialek")}
                >
                  <MessageCircle size={16} />
                  Terjemahan Dialek
                </button>
                <button
                  className={mode === "Info Kelantan" ? "active" : ""}
                  type="button"
                  onClick={() => setMode("Info Kelantan")}
                >
                  <Compass size={16} />
                  Pelancongan
                </button>
              </div>
            </div>
            <div className="chat-workspace">
            <section className="chat-panel">
              <div className="prompt-row">
                {(mode === "Terjemahan Dialek" ? dialectPrompts : kelantanPrompts).map((prompt) => (
                  <button key={prompt} type="button" onClick={() => submitPrompt(prompt)}>
                    <Sparkles size={15} />
                    {prompt}
                  </button>
                ))}
              </div>
              <div className="messages">
                {messages.map((message) => {
                  const relatedForMsg = message.role === "assistant" && message.result?.contexts?.length
                    ? catalog.filter(item => item.collection === message.result!.contexts![0].collection).slice(0, 3)
                    : [];
                  return (
                    <article className={`message ${message.role}`} key={message.id}>
                      <span className="avatar">{message.role === "assistant" ? <Bot size={18} /> : <User size={18} />}</span>
                      <div className="message-body">
                        <div className="bubble-row">
                          <div className="bubble">{message.result ? renderAnswer(message.result) : message.content}</div>
                          {message.role === "assistant" && (
                            <button
                              className="copy-btn"
                              type="button"
                              aria-label="Salin jawapan"
                              onClick={() => copyToClipboard(message.id, message.content)}
                            >
                              {copiedId === message.id ? <Check size={13} /> : <Copy size={13} />}
                            </button>
                          )}
                        </div>
                        {message.role === "assistant" && message.result?.contexts?.length ? (
                          <details className="sources">
                            <summary><Database size={11} /> {message.result.contexts.length} sumber digunakan</summary>
                            <div className="source-list">
                              {message.result.contexts.map((ctx, i) => (
                                <div className="source-item" key={i}>
                                  <span className={`item-badge badge-${ctx.collection}`}>{ctx.category}</span>
                                  <span className="source-title">{ctx.title}</span>
                                  <span className="source-score">{ctx.score.toFixed(2)}</span>
                                </div>
                              ))}
                            </div>
                          </details>
                        ) : null}
                        {relatedForMsg.length > 0 && (
                          <div className="inline-related">
                            <span className="inline-related-label"><Compass size={11} /> Item Berkaitan</span>
                            <div className="inline-related-list">
                              {relatedForMsg.map(item => (
                                <button key={item.id} type="button" className="inline-related-btn" onClick={() => submitPrompt(item.prompt, "Info Kelantan")}>
                                  <span className={`item-badge badge-${item.collection}`}>
                                    {item.collection === "tourism" ? "Tempat" : item.collection === "food" ? "Makanan" : "Budaya"}
                                  </span>
                                  {item.name}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </article>
                  );
                })}
                {loading ? (
                  <article className="message assistant">
                    <span className="avatar"><Bot size={18} /></span>
                    <div className="message-body">
                      <div className="bubble-row">
                        <div className="bubble typing"><Loader2 size={16} /> Menyemak pangkalan data...</div>
                      </div>
                    </div>
                  </article>
                ) : null}
                <div ref={messagesEndRef} />
              </div>
              <form className="composer" onSubmit={onSubmit}>
                <Search size={18} />
                <input value={input} onChange={(event) => setInput(event.target.value)} placeholder={mode === "Terjemahan Dialek" ? "Taip ayat dialek Kelantan untuk diterjemah..." : "Taip soalan tentang Kelantan..."} />
                <button disabled={loading || !input.trim()} type="submit" aria-label="Hantar">
                  <Send size={18} />
                </button>
              </form>
            </section>

            <aside className="insight-panel">
              {mode === "Terjemahan Dialek" && <TipsTerjemahan />}
              {mode === "Info Kelantan" && <TipsPelancongan />}
              {mode === "Info Kelantan" && <KawalanSkop />}
              {/* ROUGE-L and Triad RAG hidden from UI — scores still computed by backend */}
              {/* Uncomment to re-enable evaluation panel:
              <section>
                <h2><BarChart3 size={18} /> ROUGE-L</h2>
                <p className="metric-desc">Mengukur padanan token antara jawapan chatbot dengan konteks sumber yang ditemui.</p>
                <div className="metric-bars">
                  <MetricBar label="ROUGE-L" value={lastResult?.eval?.rouge_l} />
                </div>
              </section>
              <section>
                <h2><Bot size={18} /> Triad RAG</h2>
                <p className="metric-desc">Penilaian automatik menggunakan LLM-as-a-Judge — mengukur kualiti RAG dari tiga dimensi.</p>
                <div className="metric-bars">
                  <MetricBar label="Kerelevanan Konteks" value={lastResult?.eval?.judge_context_relevance} />
                  <MetricBar label="Groundedness" value={lastResult?.eval?.judge_groundedness} />
                  <MetricBar label="Kerelevanan Jawapan" value={lastResult?.eval?.judge_answer_relevance} />
                </div>
              </section>
              */}
            </aside>
            </div>
          </>
        ) : null}

        {view === "explore" ? (
          <>
            <div className="catalog-toolbar">
              <div className="catalog-toolbar-top">
                <div className="catalog-search-wrap">
                  <Search size={15} />
                  <input
                    className="catalog-search"
                    type="search"
                    placeholder="Cari nama atau penerangan..."
                    value={catalogSearch}
                    onChange={(e) => setCatalogSearch(e.target.value)}
                  />
                </div>
                <div className="catalog-filter-pills">
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
              <div className="catalog-toolbar-bottom">
                <div className="catalog-stats">
                  <span className="stat-pill badge-tourism">{catalogStats.tourism} Tempat</span>
                  <span className="stat-pill badge-food">{catalogStats.food} Makanan</span>
                  <span className="stat-pill badge-culture">{catalogStats.culture} Budaya</span>
                </div>
                <p className="catalog-count">
                  {filteredCatalog.length > 0
                    ? `${catalogPage * ITEMS_PER_PAGE + 1}–${Math.min((catalogPage + 1) * ITEMS_PER_PAGE, filteredCatalog.length)} daripada ${filteredCatalog.length} item`
                    : catalogSearch
                    ? `Tiada hasil untuk "${catalogSearch}"`
                    : "Tiada item ditemui."}
                </p>
              </div>
            </div>
            {catalog.length === 0 ? (
              <section className="explore-view">
                {Array.from({ length: 9 }, (_, i) => (
                  <div className="explore-item skeleton-card" key={i}>
                    <div className="skeleton-block" />
                    <div className="explore-item-body">
                      <div className="skeleton-line" style={{ width: "70px", height: "22px" }} />
                      <div className="skeleton-line" style={{ width: "78%", height: "20px" }} />
                      <div className="skeleton-line" style={{ height: "52px" }} />
                      <div className="skeleton-line" style={{ height: "40px" }} />
                    </div>
                  </div>
                ))}
              </section>
            ) : (
              <section className="explore-view">
                {pagedCatalog.map((item) => (
                  <article className="explore-item" key={item.id}>
                    <div className="catalog-image">
                      {catalogImages[item.id]
                        ? <img
                            src={catalogImages[item.id]}
                            alt={item.name}
                            loading="lazy"
                            style={{ opacity: 0 }}
                            onLoad={(e) => { e.currentTarget.style.opacity = "1"; }}
                          />
                        : (
                          <div className="catalog-no-image">
                            <MapPinned size={30} />
                            <span>{item.category}</span>
                          </div>
                        )
                      }
                    </div>
                    <div className="explore-item-body">
                      <span className={`item-badge badge-${item.collection}`}>{item.category}{item.district ? ` / ${item.district}` : ""}</span>
                      <h2>{item.name}</h2>
                      <p>{item.description}</p>
                      <button type="button" onClick={() => submitPrompt(item.prompt, "Info Kelantan")}>
                        <MapPinned size={16} />
                        Tanya JomKecek
                      </button>
                    </div>
                  </article>
                ))}
              </section>
            )}
            {totalPages > 1 && (
              <div className="pagination">
                <button
                  className="pagination-btn"
                  disabled={catalogPage === 0}
                  type="button"
                  onClick={() => { setCatalogPage((p) => p - 1); window.scrollTo({ top: 0, behavior: "smooth" }); }}
                >
                  ← Sebelum
                </button>
                <span className="pagination-info">Halaman {catalogPage + 1} daripada {totalPages}</span>
                <button
                  className="pagination-btn"
                  disabled={catalogPage >= totalPages - 1}
                  type="button"
                  onClick={() => { setCatalogPage((p) => p + 1); window.scrollTo({ top: 0, behavior: "smooth" }); }}
                >
                  Seterusnya →
                </button>
              </div>
            )}
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
      {showScrollTop && (
        <button
          className="scroll-top-btn"
          type="button"
          aria-label="Kembali ke atas"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        >
          ↑
        </button>
      )}
      {toast && (
        <div className="toast" role="alert">{toast}</div>
      )}
    </main>
  );
}
