import math

# Standard physical properties for gas components at standard conditions
# Molecular Weight (MW) in lb/lb-mol, Liquid Density (rho) in lb/gal
GAS_PROPERTIES = {
    'C1':  {'MW': 16.043, 'rho_liquid': 2.50},  # Methane
    'C2':  {'MW': 30.070, 'rho_liquid': 2.97},  # Ethane
    'C3':  {'MW': 44.097, 'rho_liquid': 4.23},  # Propane
    'C4+': {'MW': 58.120, 'rho_liquid': 4.86},  # Butane+ (using n-butane as proxy)
    'N2':  {'MW': 28.013, 'rho_liquid': 6.74},  # Nitrogen
    'CO2': {'MW': 44.010, 'rho_liquid': 8.50},  # Carbon Dioxide
    'H2S': {'MW': 34.080, 'rho_liquid': 7.97}   # Hydrogen Sulfide
}


def calculate_recoverable_volumes(flare_mmscfd, asset_category, recovery_factor=0.85):
    """
    Calculates recoverable volumes while adjusting for the asset's flaring baseline.
    Upgraded to formally separate Q_design (peak capacity for sizing) from 
    Q_annual (for economics) using dimensionless downtime logic.
    """
    if asset_category == "Non-AG_Forfeiture_Risk":
        operational_days_flaring = 365  # Continuous routine flaring
    elif asset_category == "Active_AG_Upset_Audit":
        operational_days_flaring = 60   # Cumulative trips/upsets per year
    else:
        operational_days_flaring = 365

    # 1. Calculate fractional downtime mathematically
    f_down = (365 - operational_days_flaring) / 365.0

    # 2. Peak daily gas recovered when the flare is active (Q_design)
    daily_recoverable_gas = flare_mmscfd * recovery_factor
    residual_flare = flare_mmscfd - daily_recoverable_gas
    
    # 3. Annual volume restricted by fractional downtime math
    annual_recoverable_mmscf = daily_recoverable_gas * 365 * (1 - f_down)

    return {
        "daily_recoverable_mmscfd": round(daily_recoverable_gas, 2),
        "design_capacity_mmscfd": round(daily_recoverable_gas, 2), # Passed to equipment sizing
        "residual_flare_mmscfd": round(residual_flare, 2),
        "annual_recoverable_mmscf": round(annual_recoverable_mmscf, 2),
        "flaring_days_per_year": operational_days_flaring,
        "f_down": round(f_down, 4)
    }


def calculate_gpm(mole_fractions):
    """
    Calculates the Gallons per Thousand Cubic Feet (GPM) for condensable components.
    Uses 379.4 scf/lb-mol as the standard molar volume.
    """
    gpm_results = {}
    for comp, zi in mole_fractions.items():
        if comp in ['C2', 'C3', 'C4+']:
            mw = GAS_PROPERTIES[comp]['MW']
            rho = GAS_PROPERTIES[comp]['rho_liquid']
            
            # GPM_i = (z_i * 1000 / 379.4) * (MW_i / rho_liquid_i)
            gpm_i = (zi * 1000 / 379.4) * (mw / rho)
            gpm_results[comp] = round(gpm_i, 3)
            
    gpm_results['Total_C3+'] = round(gpm_results.get('C3', 0) + gpm_results.get('C4+', 0), 3)
    return gpm_results


def calculate_component_volumes(daily_recoverable_mmscfd, mole_fractions):
    """
    Breaks down the gas stream into distinct commercial products.
    UPGRADE: Replaces flat percentages with dynamic GPM physical derivations 
    via component-specific liquid densities.
    """
    # Calculate precise GPM yields
    gpm_yields = calculate_gpm(mole_fractions)
    
    # Methane volume tracks the C1 dry gas fraction
    c1_fraction = mole_fractions.get('C1', 0.70) 
    methane_mmscfd = daily_recoverable_mmscfd * c1_fraction
    
    # LPG Liquids: Convert daily MMSCFD to Gallons per Day (GPD) using GPM
    # Formula: (MMSCFD * 1000 to get MSCFD) * GPM = GPD
    lpg_gpm = gpm_yields.get('Total_C3+', 0)
    lpg_gallons_per_day = (daily_recoverable_mmscfd * 1000) * lpg_gpm
    
    return {
        "methane_mmscfd": round(methane_mmscfd, 2),
        "lpg_liquids_gpd": round(lpg_gallons_per_day, 2),
        "gpm_yields": gpm_yields
    }


def generate_risk_matrix(asset_category, recommended_route):
    """
    Generates a dynamic Risk Assessment Matrix (RAM) tailored to the specific 
    facility baseline and the app's top recommended commercial route.
    """
    risks = []

    # 1. Base risks defined by the facility's current situation
    if asset_category == "Active_AG_Upset_Audit":
        risks.extend([
            {"Risk": "Upstream Backpressure", "Impact": "High", "Probability": "High", "Mitigation": "Retain safety flare fallback; utilize modular backup sizing to prevent oil production bottlenecks."},
            {"Risk": "Variable Upset Flow", "Impact": "Medium", "Probability": "High", "Mitigation": "Ensure wide turndown capability in secondary gas handling equipment."}
        ])
    elif asset_category == "Non-AG_Forfeiture_Risk":
        risks.extend([
            {"Risk": "Capital Overrun", "Impact": "High", "Probability": "Medium", "Mitigation": "Deploy standardized modular skids rather than bespoke stick-built facilities."},
            {"Risk": "Asset Forfeiture", "Impact": "Critical", "Probability": "Medium", "Mitigation": "Accelerate low-capex collocated off-taker deployment to achieve immediate compliance."}
        ])

    # 2. Route-specific risks
    if recommended_route == "GAS_NETWORK_TIE_IN":
        risks.append({"Risk": "Pipeline Sabotage", "Impact": "High", "Probability": "Medium", "Mitigation": "Bury tie-in lines; execute community engagement and surveillance."})
    elif recommended_route == "COLLOCATED_OFFTAKER":
        risks.append({"Risk": "Off-taker Default", "Impact": "High", "Probability": "Low", "Mitigation": "Implement rigid Take-or-Pay agreements and guarantee letters of credit."})
    elif recommended_route == "CNG":
        risks.append({"Risk": "Logistics Failure", "Impact": "Medium", "Probability": "High", "Mitigation": "Maintain N+2 truck fleet redundancy; survey road conditions seasonally."})
    elif recommended_route == "LPG_NGL":
        risks.append({"Risk": "Storage Saturation", "Impact": "High", "Probability": "Medium", "Mitigation": "Ensure continuous truck evacuation to prevent forced upstream shutdowns."})
    
    return risks