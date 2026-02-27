"""
QuantScale AI - Streamlit Frontend (Main App)
Directly imports QuantScaleSystem - no HTTP dependency needed.
"""
import re
import pandas as pd
import streamlit as st
from core.schema import OptimizationRequest

# --- Page Config ---
st.set_page_config(
    page_title="QuantScale AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background-color: #0f1117; }
    .main-header {
        background: linear-gradient(90deg, #60a5fa, #34d399);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        padding-top: 1rem;
    }
    .sub-header {
        color: #94a3b8;
        font-size: 1.1rem;
        text-align: center;
        margin-bottom: 2rem;
    }
    div[data-testid="metric-container"] {
        background-color: #1e212b;
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 1rem;
    }
    .section-title {
        color: #94a3b8;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
        margin-bottom: 0.5rem;
        margin-top: 1.5rem;
    }
    .narrative-box {
        background-color: #1e212b;
        border-left: 4px solid #10b981;
        padding: 1.5rem;
        border-radius: 0 12px 12px 0;
        line-height: 1.8;
        color: #e2e8f0;
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Parsers ---
def parse_investment_amount(text: str) -> float:
    text = text.replace(",", "")
    match = re.search(r'\$?([\d.]+)\s*([kKmM]?)', text)
    if match:
        amount = float(match.group(1))
        suffix = match.group(2).lower()
        if suffix == 'k': amount *= 1_000
        elif suffix == 'm': amount *= 1_000_000
        return amount
    return 100_000.0


def parse_strategy(text: str):
    lower = text.lower()
    strategy, top_n = None, None
    if "smallest" in lower:
        strategy = "smallest_market_cap"
    elif "largest" in lower:
        strategy = "largest_market_cap"
    if strategy:
        match = re.search(r'(\d+)\s*(?:smallest|largest|companies|stocks)', lower)
        top_n = int(match.group(1)) if match else 50
    return strategy, top_n


def build_portfolio_df(allocations: dict, investment: float) -> pd.DataFrame:
    rows = []
    for ticker, weight in sorted(allocations.items(), key=lambda x: x[1], reverse=True):
        rows.append({
            "Ticker": ticker,
            "Allocation (%)": f"{weight * 100:.2f}%",
            "Investment ($)": f"${weight * investment:,.2f}"
        })
    return pd.DataFrame(rows)


# --- Lazy-load system to avoid import overhead on every rerender ---
@st.cache_resource(show_spinner="Loading QuantScale Engine...")
def get_system():
    from main import QuantScaleSystem
    return QuantScaleSystem()


# --- UI ---
st.markdown('<div class="main-header">QuantScale AI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Direct Indexing & Attribution Engine</div>', unsafe_allow_html=True)

user_input = st.text_area(
    "",
    placeholder="Describe your goal, e.g., 'Optimize my $10,000 portfolio but exclude the Energy sector.'",
    height=100,
    label_visibility="collapsed"
)
run_btn = st.button("🚀 Generate Portfolio Strategy", use_container_width=True, type="primary")

if run_btn and user_input:
    investment_amount = parse_investment_amount(user_input)
    strategy, top_n = parse_strategy(user_input)

    request = OptimizationRequest(
        client_id="StreamlitUser",
        initial_investment=investment_amount,
        excluded_sectors=[], # Let the LLM derive this
        excluded_tickers=[],
        strategy=strategy,
        top_n=top_n,
        benchmark="^GSPC",
        user_prompt=user_input
    )

    with st.spinner("⚙️ Running Convex Optimization & AI Analysis..."):
        try:
            system = get_system()
            result = system.run_pipeline(request)
        except Exception as e:
            st.error(f"❌ Optimization error: {e}")
            st.stop()

    if not result:
        st.error("Pipeline returned no result. Check your input.")
        st.stop()

    opt = result["optimization"]
    commentary = result["commentary"]

    # --- Metrics ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💼 Invested", f"${investment_amount:,.0f}")
    with col2:
        st.metric(
            "📊 Tracking Error",
            f"{opt.tracking_error * 100:.4f}%",
            help="How closely the portfolio tracks the S&P 500"
        )
    with col3:
        excl_display = ", ".join(excluded_sectors) if excluded_sectors else "None"
        st.metric("🚫 Excluded", excl_display if len(excl_display) <= 30 else f"{len(excluded_sectors)} Sectors")

    st.divider()

    # --- AI Commentary ---
    st.markdown('<p class="section-title">AI Performance Attribution</p>', unsafe_allow_html=True)
    st.markdown(f'<div class="narrative-box">{commentary}</div>', unsafe_allow_html=True)

    st.divider()

    # --- Full Portfolio Table ---
    allocations = opt.weights
    if allocations:
        df = build_portfolio_df(allocations, investment_amount)
        total = len(df)

        st.markdown(
            f'<p class="section-title">Full Portfolio Allocation (100%) — {total} Holdings</p>',
            unsafe_allow_html=True
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Holdings", total)
        c2.metric("Largest Position", df["Ticker"].iloc[0])
        c3.metric("Smallest Position", df["Ticker"].iloc[-1])

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=min(500, 36 * total + 40),
            column_config={
                "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                "Allocation (%)": st.column_config.TextColumn("Allocation (%)", width="small"),
                "Investment ($)": st.column_config.TextColumn(
                    f"Investment (of ${investment_amount:,.0f})", width="medium"
                ),
            }
        )
# Metadata: Update trigger for build system
