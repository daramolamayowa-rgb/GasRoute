def evaluate_routes(data):
    """
    Evaluates and ranks potential gas commercialization routes based on facility data,
    thermodynamic gas composition (GPM), spatial intelligence, and utilization profiles.
    """
    
    # 1. Extract physical and commercial parameters
    # Aligning with new calculations.py outputs
    flare = data.get("design_capacity_mmscfd", data.get("flare_mmscfd", 0)) 
    asset_category = data.get("asset_category", "Non-AG_Forfeiture_Risk")
    
    # New spatial & thermodynamic properties
    location_type = data.get("location_type", "Onshore")
    gpm_yields = data.get("gpm_yields", {})
    total_c3_plus = gpm_yields.get("Total_C3+", 0.0)
    
    # Legacy parameters
    c1_percent = data.get("c1_percent", 0)          
    wobbe_index = data.get("wobbe_index", 0)        
    distance_to_network_km = data.get("distance_to_network_km", 999)
    distance_to_market_km = data.get("distance_to_market_km", 999)
    road_access = data.get("road_access", False)
    
    power_demand_mw = data.get("power_demand_mw", 0)
    collocated_demand_mmscfd = data.get("collocated_demand_mmscfd", 0)
    reinjection_suitable = data.get("reinjection_suitable", False)

    # Utilization Penalty: Upset flares run < 20% of the year. 
    # High CAPEX routes (LNG, Pipelines) become commercially unviable due to low annual throughput.
    is_upset = (asset_category == "Active_AG_Upset_Audit")
    capex_penalty = 0.3 if is_upset else 1.0

    routes = {}

    # ---------------------------------------------------------
    # ROUTE 1: GAS NETWORK TIE-IN (Direct Pipeline Sales)
    # ---------------------------------------------------------
    network_score = 20
    justification_net = []
    
    if distance_to_network_km <= 15:
        network_score += 50
        justification_net.append("Excellent proximity to gas trunkline.")
    elif distance_to_network_km <= 50:
        network_score += 25
        justification_net.append("Viable tie-in distance.")
    else:
        justification_net.append("Pipeline distance exceeds economic threshold.")
        
    if flare >= 3:
        network_score += 15
    if c1_percent >= 85 and wobbe_index > 40:
        network_score += 15

    network_score *= capex_penalty
    if is_upset: justification_net.append("Warning: Low utilization (Upset Flare) destroys pipeline ROI.")

    routes["GAS_NETWORK_TIE_IN"] = {
        "score": min(network_score, 100),
        "infrastructure": ["Metering", "Pipeline Tie-in", "Pressure Control"],
        "capex_profile": "Low to Moderate - Highly distance dependent",
        "justification": " | ".join(justification_net)
    }

    # ---------------------------------------------------------
    # ROUTE 2: COLLOCATED OFF-TAKER (Raw/Wet Gas Sales)
    # ---------------------------------------------------------
    collocated_score = 10
    justification_coll = []
    
    if collocated_demand_mmscfd > 0 and flare >= collocated_demand_mmscfd:
        collocated_score += 70
        justification_coll.append("Sufficient local demand matches flare volume.")
    elif collocated_demand_mmscfd > 0:
        collocated_score += 40
        justification_coll.append("Partial local demand identified.")
        
    if is_upset:
        justification_coll.append("Ideal for upset facilities (shifts CAPEX risk to off-taker).")

    routes["COLLOCATED_OFFTAKER"] = {
        "score": min(collocated_score, 100), # No CAPEX penalty since off-taker builds it
        "infrastructure": ["Metering", "Minimal Piping Tie-in"],
        "capex_profile": "Minimal - Off-taker handles processing",
        "justification": " | ".join(justification_coll) if justification_coll else "No local collocated demand identified."
    }

    # ---------------------------------------------------------
    # ROUTE 3: CNG (Compressed Natural Gas)
    # ---------------------------------------------------------
    cng_score = 30
    justification_cng = []
    
    if not road_access or location_type == 'Offshore':
        cng_score = 0
        justification_cng.append("Fatal Flaw: No road access or offshore site prevents truck logistics.")
    else:
        cng_score += 20
        justification_cng.append("Road access supports virtual pipeline.")
        if distance_to_market_km <= 150:
            cng_score += 20
            justification_cng.append("Target market within optimal trucking radius.")
        if flare >= 1:
            cng_score += 15
        if c1_percent >= 85:
            cng_score += 15

    cng_score *= (0.5 if is_upset else 1.0) # Moderate penalty for upset assets

    routes["CNG"] = {
        "score": min(cng_score, 100),
        "infrastructure": ["KO Drum", "Modular Compressor", "Loading Facility"],
        "capex_profile": "Moderate - Requires compression and truck logistics",
        "justification": " | ".join(justification_cng)
    }

    # ---------------------------------------------------------
    # ROUTE 4: LNG (Liquefied Natural Gas)
    # ---------------------------------------------------------
    lng_score = 20
    justification_lng = []
    
    if flare >= 5:
        lng_score += 30
        justification_lng.append("Volume supports small-scale train.")
    if c1_percent >= 90:
        lng_score += 20
        justification_lng.append("High methane purity ideal for liquefaction.")
    
    if not road_access or location_type == 'Offshore':
        lng_score = 0
        justification_lng.append("Fatal Flaw: Requires deepwater marine loading or onshore road access.")

    lng_score *= capex_penalty
    if is_upset: justification_lng.append("Warning: Cryogenic facilities require continuous baseload flow.")

    routes["LNG"] = {
        "score": min(lng_score, 100),
        "infrastructure": ["Pretreatment", "Liquefaction Unit", "Cryo Storage"],
        "capex_profile": "High - Complex cryogenic equipment",
        "justification": " | ".join(justification_lng)
    }

    # ---------------------------------------------------------
    # ROUTE 5: POWER GENERATION
    # ---------------------------------------------------------
    power_score = 25
    justification_pwr = []
    
    if power_demand_mw >= 2:
        power_score += 45
        justification_pwr.append("Strong local power demand.")
    if flare >= 1:
        power_score += 20
    if c1_percent >= 75: 
        power_score += 10

    power_score *= (0.7 if is_upset else 1.0) # Gas engines can handle some intermittent running

    routes["POWER"] = {
        "score": min(power_score, 100),
        "infrastructure": ["Gas Engine/Turbine", "Generator", "Distribution"],
        "capex_profile": "Moderate to High",
        "justification": " | ".join(justification_pwr) if justification_pwr else "Limited local power demand."
    }

    # ---------------------------------------------------------
    # ROUTE 6: LPG / NGL RECOVERY
    # ---------------------------------------------------------
    lpg_score = 15
    justification_lpg = []
    
    if not road_access or location_type == 'Offshore':
        lpg_score = 0
        justification_lpg.append("Fatal Flaw: Requires road access for bullet truck evacuation.")
    else:
        # UPGRADE: Uses dynamic GPM derived from thermodynamics rather than flat %
        if total_c3_plus >= 3.0:
            lpg_score += 50
            justification_lpg.append(f"Highly lucrative rich gas stream ({total_c3_plus:.2f} GPM).")
        elif total_c3_plus >= 1.5:
            lpg_score += 25
            justification_lpg.append(f"Viable liquid yields ({total_c3_plus:.2f} GPM).")
        else:
            justification_lpg.append(f"Lean gas ({total_c3_plus:.2f} GPM) severely limits LPG recovery.")

        if flare >= 3:
            lpg_score += 20

    lpg_score *= capex_penalty

    routes["LPG_NGL"] = {
        "score": min(lpg_score, 100),
        "infrastructure": ["NGL Recovery Unit", "Fractionation", "Pressurized Storage"],
        "capex_profile": "High - Requires fractionation towers",
        "justification": " | ".join(justification_lpg)
    }

    # ---------------------------------------------------------
    # ROUTE 7: REINJECTION / EOR
    # ---------------------------------------------------------
    reinjection_score = 10
    justification_inj = []
    
    if reinjection_suitable:
        reinjection_score += 60
        justification_inj.append("Reservoir geometry supports reinjection.")
    else:
        justification_inj.append("Reservoir not designated for gas support.")
        
    if flare >= 2:
        reinjection_score += 30

    reinjection_score *= capex_penalty

    routes["REINJECTION"] = {
        "score": min(reinjection_score, 100),
        "infrastructure": ["Heavy Compression", "Injection Well"],
        "capex_profile": "High - Specialized well interventions",
        "justification": " | ".join(justification_inj)
    }

    # 2. Sort the routes by score in descending order
    ranked_routes = sorted(
        [{"route_name": name, **details} for name, details in routes.items()],
        key=lambda x: x["score"],
        reverse=True
    )

    return ranked_routes