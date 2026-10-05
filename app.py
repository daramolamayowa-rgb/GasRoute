import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from calculations import (
    calculate_recoverable_volumes,
    calculate_component_volumes,
    generate_risk_matrix
)
from route import evaluate_routes
from economics import calculate_economics

# --- CONFIGURATION ---
st.set_page_config(
    page_title="GASROUTE 2030",
    page_icon="🔥",
    layout="wide"
)

st.title("GasRoute")
st.subheader("Intelligent gas flaring commercialization, route ranking, and boardroom decision support.")
st.markdown("---")

# --- DATA STORAGE ENGINE ---
@st.cache_data
def load_base_database():
    paths = ["facilities.csv", "data/facilities.csv"]
    for path in paths:
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                if not df.empty:
                    return df
            except Exception:
                pass
    return pd.DataFrame()

base_df = load_base_database()

# --- REPOSITORY MANAGEMENT ---
st.markdown("### 📂 Asset Repository Management")
col_upload, col_select = st.columns(2)

with col_upload:
    uploaded_file = st.file_uploader("📥 Upload Custom Facility Dataset (CSV)", type=["csv"])

db_df = base_df.copy()
if uploaded_file is not None:
    try:
        uploaded_df = pd.read_csv(uploaded_file)
        if not uploaded_df.empty and "facility_name" in uploaded_df.columns:
            db_df = pd.concat([uploaded_df, base_df], ignore_index=True).drop_duplicates(subset=["facility_name"])
            st.toast("Custom file parsed and appended successfully!", icon="✅")
    except Exception as e:
        st.error(f"Failed to read file: {e}")

if not db_df.empty:
    if "facility_name" in db_df.columns:
        db_df["facility_name"] = db_df["facility_name"].astype(str).str.strip()
    if "asset_category" in db_df.columns:
        db_df["asset_category"] = db_df["asset_category"].astype(str).str.strip()

# --- SESSION STATE INITIALIZATION ---
default_vals = {
    "flare_in": 8.5,
    "c1_in": 88.0,
    "c3c4_in": 4.5,
    "wobbe_in": 46.2,
    "dist_net_in": 85.0,
    "dist_mkt_in": 150.0,
    "power_in": 0.0,
    "colloc_in": 0.0,
    "road_in": True,
    "reinj_in": False,
    "asset_cat": "Non-AG_Forfeiture_Risk",
    "location_type_in": "Onshore",
    "oil_prod_in": 12500.0,
    "flaring_auth_in": False,
    "is_deep_in": False
}

for key, val in default_vals.items():
    if key not in st.session_state:
        st.session_state[key] = val

def on_preset_change():
    chosen = st.session_state["preset_selector"]
    if chosen != "Manual Input Only" and not db_df.empty:
        matched = db_df[db_df["facility_name"] == chosen]
        if not matched.empty:
            row = matched.iloc[0]
            st.session_state["flare_in"] = float(row.get("flare_mmscfd", 8.5))
            st.session_state["c1_in"] = float(row.get("c1_percent", 88.0))
            st.session_state["c3c4_in"] = float(row.get("c3_c4_percent", 4.5))
            st.session_state["wobbe_in"] = float(row.get("wobbe_index", 46.2))
            st.session_state["dist_net_in"] = float(row.get("distance_to_network_km", 85.0))
            st.session_state["dist_mkt_in"] = float(row.get("distance_to_market_km", 150.0))
            st.session_state["power_in"] = float(row.get("power_demand_mw", 0.0))
            st.session_state["colloc_in"] = float(row.get("collocated_demand_mmscfd", 0.0))
            st.session_state["road_in"] = str(row.get("road_access", True)).strip().upper() == "TRUE"
            st.session_state["reinj_in"] = str(row.get("reinjection_suitable", False)).strip().upper() == "TRUE"
            st.session_state["asset_cat"] = str(row.get("asset_category", "Non-AG_Forfeiture_Risk"))
            st.session_state["location_type_in"] = str(row.get("location_type", "Onshore"))
            st.session_state["oil_prod_in"] = float(row.get("oil_production_bpd", 12500.0))
            st.session_state["flaring_auth_in"] = str(row.get("flaring_authorized", False)).strip().upper() == "TRUE"
            st.session_state["is_deep_in"] = str(row.get("is_deep_offshore", False)).strip().upper() == "TRUE"

with col_select:
    preset_options = ["Manual Input Only"]
    if not db_df.empty and "facility_name" in db_df.columns:
        preset_options += db_df["facility_name"].tolist()
    st.selectbox("📂 Load Profile Template Target", preset_options, key="preset_selector", on_change=on_preset_change)

st.markdown("---")

# --- SIDEBAR INPUTS ---
st.sidebar.header("🎛️ Asset Parameters")
cat_options = ["Non-AG_Forfeiture_Risk", "Active_AG_Upset_Audit", "NGFCP_Awarded_ThirdParty"]
cat_idx = cat_options.index(st.session_state["asset_cat"]) if st.session_state["asset_cat"] in cat_options else 0
asset_cat = st.sidebar.selectbox("Asset Category", cat_options, index=cat_idx)

flare = st.sidebar.number_input("Flare Volume (MMSCFD)", min_value=0.0, key="flare_in")

st.sidebar.subheader("Gas & Field Characteristics")
c1 = st.sidebar.slider("Methane (C1) %", 50.0, 100.0, key="c1_in")
c3c4 = st.sidebar.slider("LPG/NGL (C3+) %", 0.0, 20.0, key="c3c4_in")
wobbe = st.sidebar.number_input("Wobbe Index", min_value=30.0, key="wobbe_in")

loc_options = ["Onshore", "Offshore", "Swamp"]
loc_idx = loc_options.index(st.session_state["location_type_in"]) if st.session_state["location_type_in"] in loc_options else 0
location_type = st.sidebar.selectbox("Location Type", loc_options, index=loc_idx)

oil_prod = st.sidebar.number_input("Oil Production (BPD)", min_value=0.0, key="oil_prod_in")
flaring_auth = st.sidebar.checkbox("Flaring Authorized by NUPRC", key="flaring_auth_in")
is_deep = st.sidebar.checkbox("Deep Offshore Asset", key="is_deep_in")

st.sidebar.subheader("Market & Infrastructure")
dist_net = st.sidebar.number_input("Distance to Gas Network (km)", min_value=0.0, key="dist_net_in")
dist_mkt = st.sidebar.number_input("Distance to Trucking Market (km)", min_value=0.0, key="dist_mkt_in")
power_demand = st.sidebar.number_input("Local Power Demand (MW)", min_value=0.0, key="power_in")
colloc_demand = st.sidebar.number_input("Collocated Offtaker Demand (MMSCFD)", min_value=0.0, key="colloc_in")
road_access = st.sidebar.checkbox("Road / Logistics Access", key="road_in")
reinjection = st.sidebar.checkbox("Reservoir Suitable for Reinjection", key="reinj_in")

# --- BACKEND COMPUTATIONS ---
vol_data = calculate_recoverable_volumes(flare, asset_cat)

mole_fractions = {
    "C1": c1 / 100.0,
    "C3": (c3c4 * 0.6) / 100.0,
    "C4": (c3c4 * 0.4) / 100.0,
    "Total_C3+": c3c4 / 100.0
}

comp_data = calculate_component_volumes(vol_data["daily_recoverable_mmscfd"], mole_fractions)

facility_data = {
    "design_capacity_mmscfd": flare,
    "flare_mmscfd": flare,
    "c1_percent": c1,
    "c3_c4_percent": c3c4,
    "wobbe_index": wobbe,
    "distance_to_network_km": dist_net,
    "distance_to_market_km": dist_mkt,
    "power_demand_mw": power_demand,
    "collocated_demand_mmscfd": colloc_demand,
    "road_access": road_access,
    "reinjection_suitable": reinjection,
    "asset_category": asset_cat,
    "location_type": location_type,
    "oil_production_bpd": oil_prod,
    "flaring_authorized": flaring_auth,
    "is_deep_offshore": is_deep,
    "gpm_yields": comp_data.get("gpm_yields", {"Total_C3+": c3c4 * 0.8})
}

ranked_routes = evaluate_routes(facility_data)
top_route = ranked_routes[0]

capex_multipliers = {
    "GAS_NETWORK_TIE_IN": 500_000, "COLLOCATED_OFFTAKER": 250_000, "CNG": 1_200_000,
    "LNG": 4_500_000, "POWER": 1_800_000, "LPG_NGL": 2_500_000, "REINJECTION": 1_400_000
}
base_capex = capex_multipliers.get(top_route["route_name"], 1_000_000) * vol_data["daily_recoverable_mmscfd"]
annual_opex = base_capex * 0.08

econ_metrics = calculate_economics(vol_data["daily_recoverable_mmscfd"], base_capex, annual_opex)
risks = generate_risk_matrix(asset_cat, top_route["route_name"])

# ==========================================
# EXECUTIVE TAB WORKFLOW
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Asset Intelligence & Route Ranking", 
    "💰 Financial & Commercial Structuring", 
    "🌪️ Risk & Sensitivity Analysis", 
    "🏛️ Boardroom Action Directives"
])

# --- TAB 1: ROUTE RANKING ---
with tab1:
    st.header("Section 1: Stranded Asset Intelligence & Route Ranking", divider="blue")
    
    p1, p2, p3 = st.columns(3)
    p1.metric("Baseline Condition", asset_cat.replace("_", " "))
    p1.metric("Operating Flaring Days/Yr", vol_data["flaring_days_per_year"])
    p2.metric("Daily Recoverable Gas", f"{vol_data['daily_recoverable_mmscfd']} MMSCFD")
    p2.metric("LPG Liquids Potential", f"{comp_data.get('lpg_liquids_gpd', 0):,.0f} GPD")
    p3.metric("Methane (C1) Purity", f"{c1}%")
    p3.metric("Distance to Grid Tie-in", f"{dist_net} km (Stranded)")

    st.markdown("---")
    st.subheader("Algorithmic Route Viability Mapping")
    route_df = pd.DataFrame(ranked_routes)
    fig = px.bar(
        route_df, x="route_name", y="score", range_y=[0, 100],
        title="Comparative Feasibility Score Mapping", color="score",
        color_continuous_scale=["#FF4B4B", "#F1C40F", "#2ECC71"], text="score"
    )
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    st.success(f"### 🏆 Primary Recommendation: **{top_route['route_name']}**")
    st.write(f"**Justification:** {top_route.get('justification', 'High commercial alignment with field parameters.')}")
    st.write(f"**Required Infrastructure:** {', '.join(top_route['infrastructure'])}")
    st.write(f"**CapEx Profile:** {top_route['capex_profile']}")

# --- TAB 2: COMMERCIAL STRUCTURING ---
with tab2:
    st.header("Section 2: Commercial Structuring (Option A vs Option B)", divider="blue")
    st.markdown("Contrasting direct JV balance sheet funding (Option A) with midstream third-party BOOT outsourcing (Option B).")

    opt_a = econ_metrics["option_a_internal"]
    opt_b = econ_metrics["option_b_outsourced"]

    col_opt_a, col_opt_b = st.columns(2)

    with col_opt_a:
        with st.container(border=True):
            st.subheader("Option A: Internal JV Funding")
            st.caption("100% Renaissance Funded | Full Revenue Retention")
            st.metric("Renaissance CAPEX", f"${opt_a['capex_usd']/1_000_000:.2f}M")
            st.metric("Project NPV (15%)", f"${opt_a['npv15_usd']/1_000_000:.2f}M")
            st.metric("Internal IRR", f"{opt_a['irr_percent']}%")
            st.metric("Payback Period", f"{opt_a['payback_years']} Years" if opt_a['payback_years'] else "N/A")

    with col_opt_b:
        with st.container(border=True):
            st.subheader("Option B: Midstream BOOT Outsourcing")
            st.caption("0% Renaissance CAPEX | Third-Party Financed | Zero Capital Risk")
            st.metric("Renaissance CAPEX", "$0.00 M", delta="100% Capital Saved", delta_color="normal")
            st.metric("NPV (15%) to Renaissance", f"${opt_b['npv15_usd']/1_000_000:.2f}M", help="Includes host fees + avoided fines")
            st.metric("Annual Value Delivered", f"${opt_b['annual_net_benefit_usd']/1_000_000:.2f}M/yr")
            st.metric("Payback Period", "Immediate (Day 1)", delta="No Capital Exposed")

# --- TAB 3: RISK & SENSITIVITY ---
with tab3:
    st.header("Section 3: Risk Assessment & Sensitivity Bounds", divider="blue")
    
    sens = econ_metrics["sensitivities"]
    base_npv_m = opt_a["npv15_usd"] / 1e6
    
    categories = list(sens.keys())
    low_swings = [sens[cat]["low"] for cat in categories]
    high_swings = [sens[cat]["high"] for cat in categories]

    t_fig = go.Figure()
    t_fig.add_trace(go.Bar(y=categories, x=low_swings, name='Downside (-20%)', orientation='h', marker=dict(color='#FF4B4B')))
    t_fig.add_trace(go.Bar(y=categories, x=high_swings, name='Upside (+20%)', orientation='h', marker=dict(color='#2ECC71')))
    t_fig.update_layout(
        title=f"<b>NPV15 Sensitivity Bounds (Baseline: ${base_npv_m:.2f}M)</b>",
        barmode='relative', bargap=0.3,
        xaxis=dict(title="NPV Delta ($ Millions USD)", zeroline=True, zerolinecolor="white"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(t_fig, use_container_width=True)

    st.markdown("#### Dynamic Risk Assessment Matrix")
    st.table(pd.DataFrame(risks))

# --- TAB 4: BOARDROOM DIRECTIVES ---
with tab4:
    st.header("Section 4: Executive Directives & ESG Profile", divider="blue")
    
    if asset_cat == "Non-AG_Forfeiture_Risk":
        directive_title = "EXECUTE THIRD-PARTY MIDSTREAM OUTSOURCING (BOOT)"
        action_steps = [
            "**Issue Expression of Interest (EOI):** Release midstream off-taker tender within 30 days to eliminate NUPRC forfeiture risk.",
            "**Capital Preservation:** Approve $0 JV CAPEX model (Option B) to shield balance sheet while ensuring 100% compliance.",
            "**Regulatory Filing:** Submit official commercialization pathway plan to NUPRC to suspend daily penalty accruals."
        ]
    elif asset_cat == "Active_AG_Upset_Audit":
        directive_title = "OPERATIONAL UPSET RELIABILITY AUDIT"
        action_steps = [
            "**Compressor Reliability Audit:** Review trip frequencies and buy-back backpressure constraints.",
            "**Auto-Turndown Control Valves:** Install automated control systems to manage operational flare spikes.",
            "**Gas Swap Agreement:** Establish off-take relief agreements with adjacent pipeline operators."
        ]
    else:
        directive_title = "HISTORICAL BENCHMARK MONITORING"
        action_steps = ["Asset already transferred under NGFCP. Retain for comparative evaluation."]

    with st.container(border=True):
        st.subheader(f"🎯 Recommended Board Action: {directive_title}")
        st.markdown(f"**Target Route:** `{top_route['route_name']}`")
        st.markdown(f"**Asset Profile:** `{asset_cat.replace('_', ' ')}`")
        
        st.markdown("#### Immediate Execution Directives")
        for step in action_steps:
            st.markdown(f"- {step}")

    st.markdown("#### ESG & Decarbonization Profile")
    col1, col2, col3 = st.columns(3)
    co2_avoided = vol_data["daily_recoverable_mmscfd"] * 365 * 1000 * (c1/100) * 0.0192 * 28 / 1000
    
    col1.metric("CO2e Abatement Potential", f"{co2_avoided:.1f}k Tons/Yr", help="Calculated using CH4 GWP of 28")
    col2.metric("NUPRC Penalty Cleared", f"${(vol_data['daily_recoverable_mmscfd'] * 365 * 3500)/1e6:.2f}M/Yr", help="Based on $3.50/MSCF non-authorized penalty rate")
    col3.metric("ESG Rating Impact", "Tier-1 Decarbonization", delta="Zero Flare Aligned")