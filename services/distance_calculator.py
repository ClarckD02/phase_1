"""
Inputs  : subject_address (str)
          surrounding_addresses (list[str])
Outputs : subject_polygon (GeoJSON)
          results (list[dict])  – distance info per surrounding parcel
Env vars : PRECISELY_CLIENT_ID and PRECISELY_CLIENT_SECRET for OAuth token acquisition
"""

# ── 1. Ensure dependencies ────────────────────────────────────────────────────
import importlib, subprocess, sys

def ensure(pkg_spec: str):
    pkg_name = pkg_spec.split("==")[0]
    try:
        importlib.import_module(pkg_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_spec, "-q"])

for spec in ("shapely==2.0.4", "pyproj", "geographiclib", "requests"):
    ensure(spec)

# ── 2. Import modules ──────────────────────────────────────────────────────────
import os, time, requests
from shapely.geometry import shape
from shapely.ops import nearest_points
from geographiclib.geodesic import Geodesic

# ── 3. OAuth2 Client-Credentials setup (per Precisely docs) ───────────────────
AUTH_URL      = "https://api.precisely.com/oauth/token"
API_URL       = "https://api.precisely.com/property/v2/parcelboundary/byaddress"
CLIENT_ID     = "mWf9rmwOkL36767kksvAVianIyuohzW8"
CLIENT_SECRET = "63Ma28PxCGId1xrw"
if not (CLIENT_ID and CLIENT_SECRET):
    raise RuntimeError(
        "Please set PRECISELY_CLIENT_ID and PRECISELY_CLIENT_SECRET environment variables"
    )

class TokenManager:
    def __init__(self, auth_url: str, client_id: str, client_secret: str):
        self.auth_url      = auth_url
        self.client_id     = client_id
        self.client_secret = client_secret
        self.token         = None
        self.expiry        = 0.0

    def get_token(self) -> str:
        now = time.time()
        if self.token is None or now >= (self.expiry - 60):
            # Precisely docs: Basic {base64(API_KEY:SECRET)}, form-data grant_type
            resp = requests.post(
                self.auth_url,
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            self.token  = data.get("access_token")
            # expiresIn is in seconds
            self.expiry = now + float(data.get("expiresIn", data.get("expires_in", 3600)))
        return self.token

# instantiate token manager
token_mgr = TokenManager(AUTH_URL, CLIENT_ID, CLIENT_SECRET)

# header helper
def _get_headers() -> dict:
    return {"Authorization": f"Bearer {token_mgr.get_token()}"}

# ── 4. Fetch polygon, coercing fallback coords ────────────────────────────────
def fetch_polygon(addr: str) -> dict:
    r = requests.get(API_URL, params={"address": addr}, headers=_get_headers(), timeout=10)
    r.raise_for_status()
    j = r.json()

    geom = j.get("geometry")
    if geom and isinstance(geom.get("coordinates"), list):
        return geom

    center = j.get("center", {})
    coords = center.get("coordinates")
    if isinstance(coords, dict):
        lon = coords.get("x") or coords.get("longitude")
        lat = coords.get("y") or coords.get("latitude")
        coords = [lon, lat]
    if isinstance(coords, (list, tuple)) and len(coords) == 2:
        return {"type": center.get("type", "Point"),
                "coordinates": [float(coords[0]), float(coords[1])]} 
    raise ValueError(f"No valid geometry or center for address '{addr}': {j}")

# ── 5. Compute geodesic distance in meters ────────────────────────────────────
def geodesic_m(poly1: dict, poly2: dict) -> float:
    p1, p2 = nearest_points(shape(poly1), shape(poly2))
    inv     = Geodesic.WGS84.Inverse(p1.y, p1.x, p2.y, p2.x)
    return inv.get("s12")

# ── 5b. Bearing and compass direction helpers ────────────────────────────────
def _azimuth_deg(lat1, lon1, lat2, lon2):
    inv = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)
    return (inv["azi1"] + 360.0) % 360.0  # 0..360

def _compass_label(bearing_deg: float, n: int = 8) -> str:
    names_8  = ["N","NE","E","SE","S","SW","W","NW"]
    names_16 = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    names = names_8 if n == 8 else names_16
    sector = round(bearing_deg / (360.0 / len(names))) % len(names)
    return names[sector]

def distance_and_direction(poly1: dict, poly2: dict, zero_thresh_m: float = 1.0, n_winds: int = 8):
    """
    Returns (distance_m, bearing_deg, compass_label)
    - Uses nearest points for consistency with your distance metric
    - Falls back to representative points if parcels touch or overlap
    """
    g1 = shape(poly1)
    g2 = shape(poly2)

    # nearest-point pair between the two geometries
    p1, p2 = nearest_points(g1, g2)
    inv = Geodesic.WGS84.Inverse(p1.y, p1.x, p2.y, p2.x)
    d_m = inv["s12"]

    if d_m >= zero_thresh_m:
        bearing = (inv["azi1"] + 360.0) % 360.0
        return d_m, bearing, _compass_label(bearing, n_winds)

    # fallback if touching or overlapping
    r1 = g1.representative_point()
    r2 = g2.representative_point()
    bearing = _azimuth_deg(r1.y, r1.x, r2.y, r2.x)
    inv2 = Geodesic.WGS84.Inverse(r1.y, r1.x, r2.y, r2.x)
    return inv2["s12"], bearing, _compass_label(bearing, n_winds)

# ── helper: never let a single bad address crash the run ───────────────
def safe_fetch_polygon(addr: str) -> tuple[dict | None, str | None]:
    """
    Returns (polygon, None) if successful, (None, error_msg) if anything fails.
    """
    try:
        return fetch_polygon(addr), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def tool_calculate_distances(subject_address, surrounding_addresses):
    """Calculate distances and return simplified data for Section 5.2.2"""
    
    # ── 7. Calculate distances  (robust version) ────────────────────────────
    subject_polygon, err = safe_fetch_polygon(subject_address)
    if subject_polygon is None:
        raise RuntimeError(f"Subject address invalid → {err}")

    results = []
    failed = []

    for addr in surrounding_addresses:
        poly, err = safe_fetch_polygon(addr)
        if poly is None:                           # lookup failed
            failed.append({"address": addr, "error": err})
            continue

        # NEW ❱❱ wrap the distance math so geometry errors don't crash the run
        try:
            d_m, bearing_deg, direction = distance_and_direction(subject_polygon, poly)
        except Exception as exc:
            failed.append({
                "address": addr,
                "error": f"Distance calc failed → {type(exc).__name__}: {exc}",
                "raw_polygon": poly
            })
            continue

        results.append({
            "address":      addr,
            "distance_m":   d_m,
            "distance_ft":  d_m * 3.28084,
            "distance_mi":  (d_m * 3.28084) / 5280,
            "bearing_deg":  bearing_deg,     # numeric 0..360, 0 = North
            "direction":    direction,       # N, NE, E, SE, S, SW, W, NW
            "polygon":      poly,
        })
    
    # Return simplified format for Section 5.2.2
    distance_data = []
    for result in results:
        distance_data.append({
            "address": result["address"],
            "distance_ft": round(result["distance_ft"], 1),  # Round to 1 decimal place
            "direction": result["direction"],
            "bearing_deg": round(result["bearing_deg"], 1)
        })
    
    return {
        "subject_address": subject_address,
        "distances": distance_data,
        "failed": failed
    }
     

def main():
    result = tool_calculate_distances("1180 WERNSING RD, JASPER, IN 47546", ["1415 MARTIN LUTHER KING JR. DRIVE, NORTH CHICAGO, IL 60064", "652 NORTH YORK RD, ELMHURST, IL 60126"])
    print(result)
if __name__ == "__main__": 
    main()
     