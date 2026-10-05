import numpy as np
import numpy_financial as npf

def calculate_flare_penalty(oil_production_bpd: float, gas_flared_mscf: float, flaring_authorized: bool = True) -> float:
    """
    Calculates the NUPRC flaring penalty based on production tiers and authorization status.
    """
    if not flaring_authorized:
        penalty_rate = 3.50  # Stricter administrative penalty rate for unauthorized flaring
    elif oil_production_bpd >= 10000:
        penalty_rate = 2.00  # Base rate for high-producing fields
    else:
        penalty_rate = 0.50  # Base rate for marginal/low-producing fields
        
    return gas_flared_mscf * penalty_rate

def calculate_pia_taxes(revenue: float, opex: float, depreciation: float, is_deep_offshore: bool = False) -> dict:
    """
    Calculates the Companies Income Tax (CIT) and Hydrocarbon Tax (HT) under the Petroleum Industry Act (PIA).
    """
    taxable_income = max(0, revenue - opex - depreciation)
    
    # 30% CIT standard for downstream/midstream gas operations
    cit_rate = 0.30 
    
    # HT applies to upstream, but typically zero-rated or exempt for standalone gas utilization 
    # depending on the specific fiscal license. We assign 15% for onshore/shallow mixed development.
    ht_rate = 0.0 if is_deep_offshore else 0.15 
    
    cit_liability = taxable_income * cit_rate
    ht_liability = taxable_income * ht_rate
    
    return {
        'Taxable_Income': taxable_income,
        'CIT': cit_liability,
        'HT': ht_liability,
        'Total_Tax': cit_liability + ht_liability
    }

def calculate_economics(recovered_gas_mmscfd, capex, annual_opex, oil_production_bpd=15000, gas_price_usd_mmbtu=2.42, flaring_authorized=True, is_deep_offshore=False):
    """
    Computes comparative economic metrics for:
    Option A: 100% Renaissance Internal CAPEX Investment
    Option B: Third-Party Midstream Outsourcing (BOOT Model - $0 CAPEX to Renaissance)
    """
    annual_volume_mmscf = recovered_gas_mmscfd * 365.0
    annual_volume_mscf = annual_volume_mmscf * 1000.0
    annual_mmbtu = annual_volume_mmscf * 1000.0
    
    # Gross energy sales & dynamic penalty avoidance
    gross_revenue_usd = annual_mmbtu * gas_price_usd_mmbtu
    avoided_penalty_usd = calculate_flare_penalty(oil_production_bpd, annual_volume_mscf, flaring_authorized)
    
    # --- OPTION A: 100% Internal JV ---
    royalty_opt_a = gross_revenue_usd * 0.05  # 5% PIA royalty
    
    # Tax Calculation (Straight-line depreciation over 10 years assumed for modeling)
    annual_depreciation = capex / 10.0 if capex > 0 else 0.0
    taxes_opt_a = calculate_pia_taxes(gross_revenue_usd, annual_opex + royalty_opt_a, annual_depreciation, is_deep_offshore)
    
    annual_net_cf_opt_a = gross_revenue_usd + avoided_penalty_usd - annual_opex - royalty_opt_a - taxes_opt_a['Total_Tax']
    
    cash_flows_a = [-capex] + [annual_net_cf_opt_a] * 10
    npv15_a = npf.npv(0.15, cash_flows_a)
    irr_a = npf.irr(cash_flows_a) * 100.0 if capex > 0 else 0.0
    payback_a = capex / annual_net_cf_opt_a if annual_net_cf_opt_a > 0 else None

    # --- OPTION B: Third-Party Outsourcing (Renaissance gets $0.40/MMBtu host fee, 0 CAPEX, 0 OPEX) ---
    host_royalty_fee_usd = annual_mmbtu * 0.40
    taxes_opt_b = calculate_pia_taxes(host_royalty_fee_usd, 0.0, 0.0, is_deep_offshore)
    annual_net_cf_opt_b = host_royalty_fee_usd + avoided_penalty_usd - taxes_opt_b['Total_Tax']
    
    cash_flows_b = [0.0] + [annual_net_cf_opt_b] * 10
    npv15_b = npf.npv(0.15, cash_flows_b)

    # --- SENSITIVITIES (+/- 20% Bounds on Option A) ---
    # Gas Price Sensitivity (Requires tax recalculation)
    cf_gas_low_rev = gross_revenue_usd * 0.8
    cf_gas_low_tax = calculate_pia_taxes(cf_gas_low_rev, annual_opex + (cf_gas_low_rev * 0.05), annual_depreciation, is_deep_offshore)['Total_Tax']
    cf_gas_low = cf_gas_low_rev + avoided_penalty_usd - annual_opex - (cf_gas_low_rev * 0.05) - cf_gas_low_tax

    cf_gas_high_rev = gross_revenue_usd * 1.2
    cf_gas_high_tax = calculate_pia_taxes(cf_gas_high_rev, annual_opex + (cf_gas_high_rev * 0.05), annual_depreciation, is_deep_offshore)['Total_Tax']
    cf_gas_high = cf_gas_high_rev + avoided_penalty_usd - annual_opex - (cf_gas_high_rev * 0.05) - cf_gas_high_tax

    npv_gas_low_delta = npf.npv(0.15, [-capex] + [cf_gas_low] * 10) - npv15_a
    npv_gas_high_delta = npf.npv(0.15, [-capex] + [cf_gas_high] * 10) - npv15_a

    # CAPEX Sensitivity (Impacts depreciation and tax deductions)
    cf_capex_low_tax = calculate_pia_taxes(gross_revenue_usd, annual_opex + royalty_opt_a, (capex * 0.8) / 10.0, is_deep_offshore)['Total_Tax']
    cf_capex_low = gross_revenue_usd + avoided_penalty_usd - annual_opex - royalty_opt_a - cf_capex_low_tax
    npv_capex_low_delta = npf.npv(0.15, [-(capex * 0.8)] + [cf_capex_low] * 10) - npv15_a

    cf_capex_high_tax = calculate_pia_taxes(gross_revenue_usd, annual_opex + royalty_opt_a, (capex * 1.2) / 10.0, is_deep_offshore)['Total_Tax']
    cf_capex_high = gross_revenue_usd + avoided_penalty_usd - annual_opex - royalty_opt_a - cf_capex_high_tax
    npv_capex_high_delta = npf.npv(0.15, [-(capex * 1.2)] + [cf_capex_high] * 10) - npv15_a

    sensitivities = {
        "Gas Price (+/-20%)": {"low": npv_gas_low_delta / 1e6, "high": npv_gas_high_delta / 1e6},
        "CAPEX (+/-20%)": {"low": npv_capex_low_delta / 1e6, "high": npv_capex_high_delta / 1e6}
    }

    return {
        "annual_gross_revenue_usd": gross_revenue_usd,
        "flare_penalty_avoided_usd": avoided_penalty_usd,
        "option_a_internal": {
            "capex_usd": capex,
            "annual_net_cash_flow_usd": annual_net_cf_opt_a,
            "annual_total_tax_usd": taxes_opt_a['Total_Tax'],
            "npv15_usd": npv15_a,
            "irr_percent": round(irr_a, 2) if not np.isnan(irr_a) else 0.0,
            "payback_years": round(payback_a, 2) if payback_a else None
        },
        "option_b_outsourced": {
            "capex_usd": 0.0,
            "annual_host_fee_usd": host_royalty_fee_usd,
            "annual_total_tax_usd": taxes_opt_b['Total_Tax'],
            "annual_net_benefit_usd": annual_net_cf_opt_b,
            "npv15_usd": npv15_b,
            "irr_percent": "N/A ($0 CAPEX)",
            "payback_years": 0.0
        },
        "sensitivities": sensitivities
    }