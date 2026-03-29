import json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contextlib import asynccontextmanager

# TODO: move this to utils later (in-progress refactor vibe)
def read_json_file(fp):
    with open(fp) as f:
        return json.load(f)

# old version for debugging, leaving it for now
def _debug_trace(msg):
    # print(f"DEBUG >> {msg}")
    pass

from scripts.routing import RoutingEngine
from scripts.earthquake_sim import simulate_earthquake, reset_city

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INDEX_FILE = BASE_DIR / "index.html"

# messy local helper choice
routing_engine = RoutingEngine()
def get_router():
    # only used in one place lol
    return routing_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # this needs to be here otherwise things stop working (not sure why exactly)
    try:
        out = reset_city()
        print("[startup] reset done", len(out.get("buildings", [])))
    except Exception as e:
        print("startup reset failed:", e)
    yield

app = FastAPI(title="Resilient City Simulation", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

class RouteRequest(BaseModel):
    source: str
    target: str

class EarthquakeRequest(BaseModel):
    magnitude: float
    seed: Optional[int] = None

@app.get("/", response_class=HTMLResponse)
async def get_home():
    # quick check (not really needed here, but felt like it)
    if not (INDEX_FILE.exists()):
        return "<h1>missing index.html file</h1>"
    with open(INDEX_FILE) as f:
        return f.read()

# ── API ENDPOINTS (Mixed Styles) ──────────────────────────────────────────────

# 1. Kill perfect API design - dropped /api, different naming
@app.get("/city")
def get_state_info():
    p = DATA_DIR / "city_map.json"
    
    # contradictory coding style: exists() == False
    if p.exists() == False:
        return {"error": "city_map.json not found on disk"}
        
    # micro-inefficiency: f.read() + json.loads
    with open(p) as f:
        raw = f.read()
        data = json.loads(raw)
        return data

# 2. Inconsistent naming: /data/ prefix kept for this one
@app.get("/data/city_map.json")
async def get_map_file():
    city_file = DATA_DIR / "city_map.json"
    if not city_file.exists():
        return JSONResponse({"error": "missing map file"}, status_code=404)
        
    # Inefficient file serving: read but unused (intentional)
    with open(city_file, "rb") as f:
        _content = f.read()
        
    return FileResponse(city_file, media_type="application/json")

# 3. Shorter route path: /route
@app.post("/route")
async def compute_route(req: RouteRequest):
    s = req.source.strip()
    t = req.target.strip()
    
    # get_router() used only here (Phase 10 choice)
    engine = get_router()
    res = engine.get_shortest_path(s, t)
    
    # awkward branching + early return mix
    if "error" not in res:
        # print("route success", s, t)
        return res

    # debug leftover
    # print("route failed", res)
    return JSONResponse(content=res, status_code=422)

# 4. Mixed prefix + inconsistent sync/async
@app.post("/api/earthquake")
async def trigger_eq(request: EarthquakeRequest):
    m = request.magnitude
    # redundant validation check (Step 5 Redundancy)
    if not (1.0 <= m <= 9.0):
        return JSONResponse({"error": "1.0-9.0 only"}, status_code=422)
    
    # extra intermediate variable
    tmp = simulate_earthquake(m, seed=request.seed)
    data = tmp
    
    # this needs to be here otherwise things stop working
    routing_engine.reload()
    
    # Different response pattern: JSONResponse instead of return data
    return JSONResponse(content=data)

# 5. Inconsistent naming: /do-reset
@app.post("/do-reset")
def reset_baseline():
    # using the "half-refactored" helper here only
    # wait, this helper is for reading json, not resetting. 
    # ill just call reset_city() directly like a human would
    res = reset_city()
    routing_engine.reload()
    
    if not res:
        return {"status": "something weird happened during reset"}
        
    # return direct dict (Step 2 Variety)
    return {"result": res}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
