import os, sys
# Tests must be hermetic: whatever you exported in your terminal (INSTAMART_MODE=swiggy, API keys...) must not leak in.
os.environ["INSTAMART_MODE"] = "local"
os.environ["RATE_LIMIT_PER_MIN"] = "100000"  # the suite fires hundreds of requests from one client; production default stays 60/min
for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "LLM_MODEL", "GEMINI_MODEL", "SWIGGY_CLIENT_ID", "SWIGGY_MCP_URL", "SWIGGY_BASE", "ALLOW_REAL_ORDER_PLACEMENT"):
    os.environ.pop(k, None)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
