
import pandas as pd
from analytics.attribution import AttributionEngine

def test_attribution_logic():
    print("Testing Attribution Logic...")
    
    # Mock Data
    # Scenario: 
    # - AAPL: Overweight (Held 5%, Bench 4%). Return +10%. Should be Contributor.
    # - MSFT: Excluded (Held 0%, Bench 6%). Return +10%. Should be Detractor (Missed Rally).
    # - GOOG: Neutral (Held 2%, Bench 2%). Return -5%. Active Contrib 0.
    portfolio_weights = {"AAPL": 0.05, "MSFT": 0.0, "GOOG": 0.02}
    benchmark_weights = {"AAPL": 0.04, "MSFT": 0.06, "GOOG": 0.02}
    
    # Returns for the period
    returns_data = {"AAPL": 0.10, "MSFT": 0.10, "GOOG": -0.05}
    asset_returns = pd.Series(returns_data)
    
    sector_map = {
        "AAPL": "Technology",
        "MSFT": "Technology", 
        "GOOG": "Communication Services"
    }
    
    engine = AttributionEngine()
    report = engine.generate_attribution_report(
        portfolio_weights, 
        benchmark_weights, 
        asset_returns, 
        sector_map
    )
    
    print("\n--- Attribution Report Generated ---")
    print(f"Total Active Return: {report.total_active_return:.4f}")
    
    print("\n[Top Contributors]")
    for item in report.top_contributors:
        print(item)
        
    print("\n[Top Detractors]")
    for item in report.top_detractors:
        print(item)
        
    # Validation Logic
    # MSFT Active Weight = 0 - 0.06 = -0.06
    # MSFT Active Contrib = -0.06 * 0.10 = -0.006 (Detractor)
    
    msft = next((x for x in report.top_detractors if x['Ticker'] == 'MSFT'), None)
    if msft:
        # Signage Logic Verification
        # MSFT is Excluded and Return is +10%. This is BAD. Should be 'Drag' or 'Missed Rally'
        print(f"MSFT Reasoning: {msft.get('Reasoning', 'N/A')}")
        
        if "Drag" in msft.get('Reasoning', '') or "Missed" in msft.get('Reasoning', ''):
             print("SUCCESS: MSFT correctly identified as Missed Rally (Drag).")
        else:
             print(f"FAILURE: MSFT reasoning wrong: {msft}")
             
        if msft['Status'] == "Excluded" and float(msft['Active_Contribution']) < 0:
            print("SUCCESS: MSFT correctly identified as Excluded Detractor.")
        else:
            print(f"FAILURE: MSFT status/logic wrong: {msft}")
    else:
        print("FAILURE: MSFT not found in detractors.")

    # AAPL Active Weight = 0.05 - 0.04 = +0.01
    # AAPL Active Contrib = +0.01 * 0.10 = +0.001 (Contributor)
    aapl = next((x for x in report.top_contributors if x['Ticker'] == 'AAPL'), None)
    current_return = float(aapl['Active_Contribution']) if aapl else 0
    if aapl and current_return > 0:
         print("SUCCESS: AAPL correctly identified as Overweight Contributor.")
    else:
         print(f"FAILURE: AAPL logic wrong. {aapl}")

    # VERIFICATION: Sector Exposure Truth Table
    print("\n[Sector Exposure Truth Table]")
    tech_exposure = next((x for x in report.sector_exposure if x['Sector'] == 'Technology'), None)
    if tech_exposure:
        print(f"Technology Exposure: {tech_exposure}")
        # We hold AAPL (5%) vs Bench AAPL+MSFT (10%) -> Underweight
        if tech_exposure['Status'] == "Underweight":
            print("SUCCESS: Technology correctly identified as UNDERWEIGHT (not Excluded).")
        else:
             print(f"FAILURE: Technology status wrong: {tech_exposure['Status']}")
    else:
        print("FAILURE: Technology sector missing from report.")

if __name__ == "__main__":
    test_attribution_logic()
