"""
QuantScale AI - Streamlit Frontend
Calls the existing FastAPI `/optimize` endpoint and displays the
full portfolio allocation with Investment ($) and Allocation (%).
"""
import re
import requests
import pandas as pd
import streamlit as st

# --- Page Config ---
st.set_page_config(
    page_title="QuantScale AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom dark-mode CSS
st.markdown("""
<style>
    /* Overall dark background */
    .stApp { background-color: #0f1117; }
    
    /* Header */
    .main-header {
        background: linear-gradient(90deg, #60a5fa, #34d399);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
    }
    .sub-header {
        color: #94a3b8;
        font-size: 1.1rem;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* Metric Cards */
    div[data-testid="metric-container"] {
        background-color: #1e212b;
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 1rem;
    }
    
    /* Section headers */
    .section-title {
        color: #94a3b8;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    /* Narrative / Commentary Box */
    .narrative-box {
        background-color: #1e212b;
        border-left: 4px solid #10b981;
        padding: 1.5rem;
        border-radius: 0 12px 12px 0;
        line-height: 1.8;
        color: #e2e8f0;
    }

    /* Dataframe styling override */
    .stDataFrame thead tr th {
        background-color: #1e212b !important;
        color: #94a3b8 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)

# --- Constants ---
API_BASE_URL = "http://localhost:8000"  # Change to HF Space URL in prod
SECTOR_KEYWORDS = {
    "Energy": ["energy", "oil", "gas"],
    "Technology": ["technology", "tech", "software", "it"],
    "Financials": ["financials", "finance", "banks"],
    "Healthcare": ["healthcare", "health", "pharma"],
    "Utilities": ["utilities", "utility"],
    "Materials": ["materials", "mining"],
    "Consumer Discretionary": ["consumer", "retail", "discretionary"],
    "Real Estate": ["real estate", "reit"],
    "Communication Services": ["communication", "media", "telecom"]
}
INCLUDE_KEYWORDS = ["keep", "include", "with", "stay", "portfolio", "only"]


def parse_investment_amount(text: str) -> float:
    """Extract dollar amount from natural language. Returns 100_000 as default."""
    text = text.replace(",", "")  # Remove commas: $10,000 -> $10000
    # Match patterns like $10000, $10K, 10K, 10000, 50k
    match = re.search(r'\$?([\d.]+)\s*([kKmM]?)', text)
    if match:
        amount = float(match.group(1))
        suffix = match.group(2).lower()
        if suffix == 'k':
            amount *= 1_000
        elif suffix == 'm':
            amount *= 1_000_000
        return amount
    return 100_000.0  # Default


def parse_excluded_sectors(text: str) -> list:
    """Extract sectors to exclude from natural language, respecting 'keep' intent."""
    lower = text.lower()
    excluded = []
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(k in lower for k in keywords):
            import re as _re
            inc_pattern = _re.compile(
                rf'({"|".join(INCLUDE_KEYWORDS)})\s+(the\s+)?({"|".join([sector.lower()] + keywords)})',
                _re.IGNORECASE
            )
            if not inc_pattern.search(lower):
                excluded.append(sector)
    return excluded


def parse_strategy(text: str):
    """Detect strategy keywords and Top N."""
    lower = text.lower()
    strategy = None
    top_n = None
    if "smallest" in lower:
        strategy = "smallest_market_cap"
    elif "largest" in lower:
        strategy = "largest_market_cap"
    if strategy:
        match = re.search(r'(\d+)\s*(?:smallest|largest|companies|stocks)', lower)
        top_n = int(match.group(1)) if match else 50
    return strategy, top_n


def build_portfolio_df(allocations: dict, investment: float) -> pd.DataFrame:
    """Convert raw allocation dict to a formatted DataFrame."""
    rows = []
    for ticker, weight in sorted(allocations.items(), key=lambda x: x[1], reverse=True):
        rows.append({
            "Ticker": ticker,
            "Allocation (%)": weight,
            "Investment ($)": weight * investment
        })
    df = pd.DataFrame(rows)
    df["Allocation (%)"] = df["Allocation (%)"].apply(lambda x: f"{x * 100:.2f}%")
    df["Investment ($)"] = df["Investment ($)"].apply(lambda x: f"${x:,.2f}")
    return df


# --- UI Layout ---
st.markdown('<div class="main-header">QuantScale AI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Direct Indexing & Attribution Engine</div>', unsafe_allow_html=True)

# Input
user_input = st.text_area(
    "",
    placeholder="Describe your goal, e.g., 'Optimize my $10,000 portfolio but exclude the Energy sector.'",
    height=100,
    label_visibility="collapsed"
)
run_btn = st.button("🚀 Generate Portfolio Strategy", use_container_width=True, type="primary")

# --- Main Logic ---
if run_btn and user_input:
    investment_amount = parse_investment_amount(user_input)
    excluded_sectors = parse_excluded_sectors(user_input)
    strategy, top_n = parse_strategy(user_input)

    payload = {
        "client_id": "StreamlitUser",
        "initial_investment": investment_amount,
        "excluded_sectors": excluded_sectors,
        "excluded_tickers": [],
        "strategy": strategy,
        "top_n": top_n,
        "benchmark": "^GSPC"
    }

    with st.spinner("Running Convex Optimization & AI Analysis..."):
        try:
            resp = requests.post(f"{API_BASE_URL}/optimize", json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            st.error(f"❌ API Error: {e}")
            st.stop()

    # --- Metrics Row ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "💼 Invested Amount",
            f"${investment_amount:,.0f}"
        )
    with col2:
        te = data.get("tracking_error", 0.0)
        st.metric(
            "📊 Projected Tracking Error",
            f"{te * 100:.4f}%",
            help="How closely this portfolio tracks the S&P 500. Lower = more index-like."
        )
    with col3:
        excl_text = ", ".join(excluded_sectors) if excluded_sectors else "None"
        st.metric("🚫 Excluded Sectors", excl_text if len(excl_text) < 25 else f"{len(excluded_sectors)} Sectors")

    st.divider()

    # --- AI Commentary ---
    st.markdown('<p class="section-title">AI Performance Attribution</p>', unsafe_allow_html=True)
    narrative = data.get("attribution_narrative", "No commentary generated.")
    st.markdown(f'<div class="narrative-box">{narrative}</div>', unsafe_allow_html=True)

    st.divider()

    # --- Full Portfolio Table ---
    allocations = data.get("allocations", {})
    if allocations:
        df = build_portfolio_df(allocations, investment_amount)
        total_holdings = len(df)
        
        st.markdown(
            f'<p class="section-title">Full Portfolio Allocation (100%) — {total_holdings} Holdings</p>',
            unsafe_allow_html=True
        )
        
        # Summary stats row above table
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Holdings", total_holdings)
        c2.metric("Largest Position", df["Ticker"].iloc[0] if len(df) else "—")
        c3.metric("Smallest Position", df["Ticker"].iloc[-1] if len(df) else "—")
        
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=min(400, 36 * total_holdings + 36),  # Dynamic auto-height, max 400px scrollable
            column_config={
                "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                "Allocation (%)": st.column_config.TextColumn("Allocation (%)", width="medium"),
                "Investment ($)": st.column_config.TextColumn(f"Investment ($) of ${investment_amount:,.0f}", width="medium"),
            }
        )
    else:
        st.warning("No allocation data returned from the optimizer.")
