# Asset lists live in modules/market_data.py now that asset prices are collected
# deterministically (non-agentic). Macro data is still collected agentically and
# uses the item lists below.
MACRO_ITEMS_ZH = (
    "中国GDP、CPI/PPI、PMI、社融、外储、人民币汇率、失业率；美国GDP、CPI、失业率、"
    "联邦基金利率、ISM PMI；欧盟GDP、CPI、欧央行利率；日本GDP、CPI、日央行利率；布伦特/WTI"
)
MACRO_ITEMS_EN = (
    "China GDP, CPI/PPI, PMI, TSF, forex reserves, RMB rate, unemployment; US GDP, CPI, "
    "unemployment, Fed funds, ISM PMI; EU GDP, CPI, ECB rate; Japan GDP, CPI, BOJ rate; Brent/WTI"
)
