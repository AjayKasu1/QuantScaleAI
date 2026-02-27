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


import plotly.graph_objects as go
import plotly.express as px

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
    market_data = result["market_data"]
    benchmark_weights = result["benchmark_weights"]
    sector_map = result["sector_map"]

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
        excl_display = ", ".join(request.excluded_sectors) if request.excluded_sectors else "None"
        st.metric("🚫 Excluded", excl_display if len(excl_display) <= 30 else f"{len(request.excluded_sectors)} Sectors")

    st.divider()

    # --- Advanced EDA Section ---
    st.markdown('<p class="section-title">Market Context & Portfolio EDA</p>', unsafe_allow_html=True)
    
    eda_col1, eda_col2 = st.columns([2, 1])
    
    with eda_col1:
        # 1. Performance Comparison (Trailing 30 Days)
        last_30_returns = market_data.iloc[-21:]
        
        # Portfolio vs Benchmark Cumulative Returns
        bench_daily = (last_30_returns * benchmark_weights).sum(axis=1)
        port_daily = (last_30_returns * pd.Series(opt.weights)).sum(axis=1)
        
        cum_bench = (1 + bench_daily).cumprod() * 100
        cum_port = (1 + port_daily).cumprod() * 100
        
        fig_perf = go.Figure()
        fig_perf.add_trace(go.Scatter(x=cum_bench.index, y=cum_bench, name="Benchmark (S&P 500 Proxy)", line=dict(color="#94a3b8", width=2, dash='dot')))
        fig_perf.add_trace(go.Scatter(x=cum_port.index, y=cum_port, name="Optimized Portfolio", line=dict(color="#60a5fa", width=3)))
        
        fig_perf.update_layout(
            title="Growth of $100 (Trailing 30 Days)",
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_perf, use_container_width=True)

    with eda_col2:
        # 2. Sector Weight Comparison (Bar)
        # Aggregating sector weights
        port_sector_weights = {}
        bench_sector_weights = {}
        
        for ticker, weight in opt.weights.items():
            s = sector_map.get(ticker, "Unknown")
            port_sector_weights[s] = port_sector_weights.get(s, 0) + weight
            
        for ticker, weight in benchmark_weights.items():
            s = sector_map.get(ticker, "Unknown")
            bench_sector_weights[s] = bench_sector_weights.get(s, 0) + weight
            
        all_sectors = sorted(list(set(list(port_sector_weights.keys()) + list(bench_sector_weights.keys()))))
        
        # 3. Sector Allocation Pie Chart (New)
        labels = list(port_sector_weights.keys())
        values = list(port_sector_weights.values())
        
        fig_pie = go.Figure(data=[go.Pie(
            labels=labels, 
            values=values, 
            hole=.4,
            marker=dict(colors=px.colors.qualitative.Pastel)
        )])
        
        fig_pie.update_layout(
            title="Portfolio Composition",
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=False
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        # Bar chart below pie for detailed comparison
        fig_sector = go.Figure(data=[
            go.Bar(name='Bench', x=all_sectors, y=[bench_sector_weights.get(s, 0)*100 for s in all_sectors], marker_color="#94a3b8"),
            go.Bar(name='Port', x=all_sectors, y=[port_sector_weights.get(s, 0)*100 for s in all_sectors], marker_color="#34d399")
        ])
        
        fig_sector.update_layout(
            title="Sector Match (%)",
            template="plotly_dark",
            barmode='group',
            height=250,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=10, t=30, b=10),
            showlegend=False
        )
        st.plotly_chart(fig_sector, use_container_width=True)

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
