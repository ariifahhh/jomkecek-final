import base64
import html
from pathlib import Path

import requests
import streamlit as st

from backend import chatbot_pipeline, get_metrics


st.set_page_config(page_title="JomKecek", page_icon="J", layout="wide")

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"


ASSET_ALIASES = {
    "background_splash.png": ("background_splash.png", "background_sub.png"),
    "chatbiotdialekkelantan_subtitle.png": (
        "chatbiotdialekkelantan_subtitle.png",
        "chatbiotdialekkelantan_bg.png",
    ),
}


def asset_path(name: str) -> Path | None:
    for candidate in ASSET_ALIASES.get(name, (name,)):
        path = ASSETS / candidate
        if path.exists():
            return path
    return None


def asset_uri(name: str) -> str:
    path = asset_path(name)
    if not path:
        return ""
    data = path.read_bytes()
    return f"data:image/png;base64,{base64.b64encode(data).decode()}"


@st.cache_data(show_spinner=False, ttl=3600)
def search_web_images(keyword: str, limit: int = 3) -> list[dict]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": keyword,
        "gsrnamespace": 6,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "format": "json",
        "origin": "*",
    }
    try:
        res = requests.get("https://commons.wikimedia.org/w/api.php", params=params, timeout=10)
        res.raise_for_status()
        pages = res.json().get("query", {}).get("pages", {})
        images = []
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            if info.get("url"):
                images.append(
                    {
                        "url": info["url"],
                        "title": page.get("title", keyword).replace("File:", ""),
                        "source": info.get("descriptionurl", info["url"]),
                    }
                )
        return images
    except Exception:
        return []


def inject_css() -> None:
    bg = asset_uri("background_splash.png")
    mascot = asset_uri("kijap_splash_bukamata.png")
    closed = asset_uri("kijang_splash_tutupmata.png")
    bg_layer = f'url("{bg}") center/cover fixed' if bg else "linear-gradient(135deg,#fff8ef,#ffffff)"
    st.markdown(
        f"""
<style>
:root {{
  --ink:#291713; --muted:#75534d; --line:rgba(120,24,18,.16);
  --red:#9d1010; --red2:#d72520; --paper:rgba(255,250,242,.94);
}}
.stApp {{
  color:var(--ink);
  background:linear-gradient(90deg,rgba(255,250,242,.95),rgba(255,255,255,.78)),{bg_layer};
}}
.main .block-container {{ max-width:1060px; padding-top:18px; padding-bottom:92px; }}
[data-testid="stSidebar"] {{ background:linear-gradient(180deg,#4b0808,#1c0908); }}
[data-testid="stSidebar"] * {{ color:#fff6e8; }}
[data-testid="stMetric"] {{
  background:rgba(255,255,255,.09);
  border:1px solid rgba(255,218,130,.16);
  padding:10px;
  border-radius:8px;
}}
.hero {{
  position:relative;
  min-height:150px;
  overflow:hidden;
  border-radius:8px;
  border:1px solid var(--line);
  background:var(--paper);
  padding:20px 210px 18px 22px;
  box-shadow:0 18px 48px rgba(91,15,12,.12);
}}
.hero h1 {{ margin:0; font-size:34px; line-height:1.02; color:#8d0c0c; letter-spacing:0; }}
.hero p {{ margin:8px 0 14px; color:var(--muted); max-width:650px; line-height:1.45; }}
.hero img {{ position:absolute; right:22px; bottom:-30px; width:160px; animation:float 4s ease-in-out infinite; }}
.chips {{ display:flex; flex-wrap:wrap; gap:8px; }}
.suggestion-grid {{
  display:grid;
  grid-template-columns:repeat(5, minmax(0, 1fr));
  gap:10px;
  margin:0 0 14px;
}}
.suggestion-grid [data-testid="stButton"] button {{
  min-height:64px;
  padding:10px 12px;
  white-space:normal;
  line-height:1.25;
  border-radius:8px;
}}
.mini-chip {{
  display:inline-flex;
  padding:7px 10px;
  border-radius:999px;
  border:1px solid rgba(157,16,16,.18);
  background:#fff7e7;
  color:#7c0c0c;
  font-size:13px;
  font-weight:700;
}}
.chat-list {{ display:grid; gap:10px; margin-top:16px; }}
.msg {{ display:flex; width:100%; }}
.msg.user {{ justify-content:flex-end; }}
.msg.assistant {{ justify-content:flex-start; }}
.bubble {{
  width:fit-content;
  max-width:min(720px,78%);
  padding:13px 15px;
  border-radius:8px;
  line-height:1.5;
  box-shadow:0 10px 28px rgba(70,13,9,.08);
}}
.user .bubble {{ color:white; background:linear-gradient(135deg,var(--red),var(--red2)); }}
.assistant .bubble {{ background:var(--paper); border:1px solid var(--line); }}
.section-title {{ color:#8d0c0c; font-weight:800; margin:0 0 5px; }}
.breakdown {{ margin:8px 0 0; padding-left:18px; }}
.answer-card {{
  border:1px solid var(--line);
  background:rgba(255,250,242,.92);
  border-radius:8px;
  padding:13px 14px;
  margin:8px 0;
  box-shadow:0 12px 32px rgba(72,14,10,.07);
}}
.answer-card strong {{ color:#8d0c0c; }}
.gallery {{ display:flex; gap:10px; overflow-x:auto; padding:5px 0 12px; }}
.gallery a {{
  flex:0 0 220px;
  border:1px solid var(--line);
  border-radius:8px;
  overflow:hidden;
  background:white;
  text-decoration:none;
  color:var(--ink);
}}
.gallery img {{ width:100%; height:126px; object-fit:cover; display:block; }}
.gallery span {{ display:block; padding:8px 9px; font-size:12px; font-weight:700; }}
@keyframes float {{ 0%,100%{{transform:translateY(0)}} 50%{{transform:translateY(-9px)}} }}
@keyframes blink {{ 0%,88%,100%{{content:url("{mascot}")}} 90%,96%{{content:url("{closed}")}} }}
@media(max-width:760px) {{
  .hero {{ padding:16px 118px 16px 16px; }}
  .hero h1 {{ font-size:27px; }}
  .hero img {{ width:112px; right:4px; }}
  .bubble {{ max-width:92%; }}
  .suggestion-grid {{ grid-template-columns:1fr; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults = {
        "messages": [
            {
                "role": "assistant",
                "content": "Demo boleh tanya pasal dialek Kelantan, tempat menarik, makanan, budaya atau soalan umum Kelantan.",
                "result": None,
            }
        ],
        "last_eval": None,
        "last_contexts": [],
        "last_visuals": [],
        "pending_prompt": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def sidebar() -> str:
    metrics = get_metrics()
    with st.sidebar:
        sidebar_image = asset_path("chatbiotdialekkelantan_subtitle.png")
        if sidebar_image:
            st.image(str(sidebar_image), use_container_width=True)
        else:
            st.title("JomKecek")
        mode = st.selectbox("Mod", ["Auto", "Terjemahan Dialek", "Info Kelantan"])
        st.caption(f"Model: `{metrics['model']}`")
        st.caption(f"Dataset: `{metrics['dataset']}`")
        st.caption(f"Collections: `{', '.join(metrics['collections'])}`")
        st.caption(f"{metrics['documents']} rekod dimuatkan")

        with st.expander("Evaluasi", expanded=False):
            ev = st.session_state.last_eval
            if ev:
                c1, c2 = st.columns(2)
                c1.metric("ROUGE-L", f"{ev['rouge_l']:.2f}")
                c2.metric("Setia", f"{ev['faithfulness']:.2f}")
                c3, c4 = st.columns(2)
                c3.metric("Konteks", f"{ev['context_precision']:.2f}")
                c4.metric("Relevan", f"{ev['answer_relevancy']:.2f}")
                st.metric("Makna", f"{ev['semantic_similarity']:.2f}")
                st.caption(ev["judge_reason"])
            else:
                st.caption("Metrik muncul selepas soalan dijawab.")

        if st.button("Reset", use_container_width=True):
            for key in ("messages", "last_eval", "last_contexts", "last_visuals", "pending_prompt"):
                st.session_state.pop(key, None)
            st.rerun()
    return mode


def hero() -> None:
    mascot_src = asset_uri("kijap_splash_bukamata.png")
    mascot_html = f'<img src="{mascot_src}" alt="Kijang mascot">' if mascot_src else ""
    st.markdown(
        f"""
<section class="hero">
  <h1>JomKecek</h1>
  <p>Hybrid chatbot untuk terjemahan Dialek Kelantan, pelancongan, budaya, makanan dan soalan umum Kelantan.</p>
  <div class="chips">
    <span class="mini-chip">Terjemahan terkawal</span>
    <span class="mini-chip">RAG bertapis</span>
    <span class="mini-chip">LLM terhad</span>
    <span class="mini-chip">Jawapan ringkas</span>
  </div>
  {mascot_html}
</section>
""",
        unsafe_allow_html=True,
    )


def suggestion_chips(mode: str) -> None:
    dialect_suggestions = [
        "Demo nok gi mano?",
        "Kawe nok makey nasi kerabu.",
        "Awak sedang buat apa?",
        "Orang itu datang dari Kota Bharu.",
        "Saya tidak tahu jalan pergi ke Pasar Siti Khadijah.",
    ]
    kelantan_suggestions = [
        "Apakah tempat menarik yang wajib dikunjungi di Kelantan?",
        "Senaraikan makanan tradisional Kelantan yang popular dalam kalangan pelancong.",
        "Apakah budaya atau seni tradisional yang terkenal di Kelantan?",
        "Di manakah lokasi sesuai untuk membeli cenderamata di Kelantan?",
        "Apakah aktiviti menarik yang boleh dilakukan oleh pelancong di Kelantan?",
    ]

    suggestions = dialect_suggestions if mode == "Terjemahan Dialek" else kelantan_suggestions
    if mode == "Auto":
        suggestions = [
            "Demo nok gi mano?",
            "Awak sedang buat apa?",
            "Apakah tempat menarik yang wajib dikunjungi di Kelantan?",
            "Senaraikan makanan tradisional Kelantan yang popular dalam kalangan pelancong.",
            "Apakah budaya atau seni tradisional yang terkenal di Kelantan?",
        ]

    st.markdown("<div class='suggestion-grid'>", unsafe_allow_html=True)
    cols = st.columns(len(suggestions))
    for col, text in zip(cols, suggestions):
        if col.button(text, use_container_width=True):
            st.session_state.pending_prompt = text
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def safe(text: str) -> str:
    return html.escape(str(text)).replace("\n", "<br>")


def render_result(result: dict) -> str:
    if result.get("intent") == "translation":
        trans = result["translation"]
        parts = "".join(
            f"<li><b>{safe(item['dialect'])}</b> -> {safe(item['bm'])}</li>"
            for item in trans.get("breakdown", [])
        )
        example = trans.get("example") or (
            trans["breakdown"][0]["contoh"] if trans.get("breakdown") else "Tiada contoh yakin."
        )
        meaning = trans.get("example_meaning", "")
        confidence = trans.get("confidence_label", "Rendah")
        return f"""
<div class="section-title">Terjemahan</div>
<div>{safe(trans['translation'])}</div>
<div class="section-title" style="margin-top:10px;">Pecahan</div>
<ul class="breakdown">{parts or "<li>Tiada padanan yakin.</li>"}</ul>
<div class="section-title" style="margin-top:10px;">Contoh</div>
<div>{safe(example)}</div>
{f'<div class="section-title" style="margin-top:10px;">Maksud</div><div>{safe(meaning)}</div>' if meaning else ''}
<div class="section-title" style="margin-top:10px;">Keyakinan</div>
<div>{safe(confidence)}</div>
"""

    kelantan = result.get("kelantan", {})
    items = kelantan.get("items", [])
    if not items:
        return safe(result["answer"])

    cards = "".join(
        f"""
<div class="answer-card">
  <strong>{safe(item['name'])}</strong><br>
  <span>{safe(item['description'])}</span>
</div>
"""
        for item in items
    )
    return f"<div>{safe(kelantan['summary'])}</div>{cards}"


def render_message(message: dict) -> None:
    role = message["role"]
    content = render_result(message["result"]) if message.get("result") else safe(message["content"])
    st.markdown(f"<div class='msg {role}'><div class='bubble'>{content}</div></div>", unsafe_allow_html=True)


def render_gallery(keywords: list[str]) -> None:
    images = []
    for keyword in keywords:
        images.extend(search_web_images(keyword, 2))
    if not images:
        return
    cards = "".join(
        f"""<a href="{safe(img['source'])}" target="_blank"><img src="{safe(img['url'])}"><span>{safe(img['title'])}</span></a>"""
        for img in images[:8]
    )
    st.markdown("#### Visual berkaitan")
    st.markdown(f"<div class='gallery'>{cards}</div>", unsafe_allow_html=True)


def handle_prompt(prompt: str, mode: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt, "result": None})
    with st.spinner("Kijang sedang menaip..."):
        result = chatbot_pipeline(prompt, mode)
    st.session_state.messages.append({"role": "assistant", "content": result["answer"], "result": result})
    st.session_state.last_eval = result["eval"]
    st.session_state.last_contexts = result["contexts"]
    st.session_state.last_visuals = result["visual_keywords"]


def main() -> None:
    inject_css()
    init_state()
    mode = sidebar()
    hero()
    suggestion_chips(mode)

    pending = st.session_state.pop("pending_prompt", None)
    if pending:
        handle_prompt(pending, mode)
        st.rerun()

    st.markdown("<div class='chat-list'>", unsafe_allow_html=True)
    for message in st.session_state.messages:
        render_message(message)
    st.markdown("</div>", unsafe_allow_html=True)

    prompt = st.chat_input("Taip ayat dialek atau soalan tentang Kelantan...")
    if prompt:
        handle_prompt(prompt, mode)
        st.rerun()

    render_gallery(st.session_state.last_visuals)

    if st.session_state.last_contexts:
        with st.expander("Konteks RAG"):
            for ctx in st.session_state.last_contexts:
                st.write(f"{ctx['score']:.2f} | {ctx['collection']} | {ctx['category']} | {ctx['title']}")
                st.caption(ctx["text"])


if __name__ == "__main__":
    main()
