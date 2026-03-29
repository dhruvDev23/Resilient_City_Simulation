"""
This file create the model of the city.
Saves to:
    data/city_map.json -> buildings + road intersections + road segments
    data/graph.gpickle -> NetworkX road graph for routing
"""

import json
import pickle
import os
import math
import networkx as nx

# Centering the city
latitudeCenter = 40.730
longitudeCenter = -74.000

# quick debug toggle
DEBUG = False

# Size of blocks in degrees
latitudeBlockSize = 0.0009  
longitudeBlockSize = 0.0012   
 
# fractional space for roads
roadSpaceFraction  = 0.15

# size of grid (city)
gridRowsCount = 5
gridColsCount = 5

# number of interactions of roads
totalIntersectionRows = gridRowsCount + 1
totalIntersectionCols = gridColsCount + 1

# Name of each building
cityBuildingNames = [
    "City Hall", "Library", "Police Station", "Fire Station 1", "Hospital 1",
    "Hotel", "Market Tower", "Bank", "Post Office", "School A",
    "Community Center", "Hospital 2", "Power Station", "Water Plant", "School B",
    "Apartment 1", "Apartment 2", "Apartment 3", "Office", "Warehouse",
    "Techno Park", "Civic Arena", "Media HeadQuater", "Research Lab", "Emergency Shelter",
]

# Type of buidings based of size of floors
buildingTypeProfiles = [
    {"type":"government", "floors":4},
    {"type":"civic",      "floors":3},
    {"type":"civic",      "floors":3},
    {"type":"civic",      "floors":2},
    {"type":"healthcare", "floors":6},
    {"type":"commercial", "floors":8},
    {"type":"commercial", "floors":12},
    {"type":"commercial", "floors":5},
    {"type":"civic",      "floors":2},
    {"type":"education",  "floors":3},
    {"type":"civic",      "floors":2},
    {"type":"commercial", "floors":10},
    {"type":"utility",    "floors":2},
    {"type":"utility",    "floors":2},
    {"type":"education",  "floors":3},
    {"type":"residential","floors":7},
    {"type":"residential","floors":6},
    {"type":"residential","floors":9},
    {"type":"commercial", "floors":11},
    {"type":"industrial", "floors":2},
    {"type":"civic",      "floors":3},
    {"type":"civic",      "floors":5},
    {"type":"commercial", "floors":4},
    {"type":"research",   "floors":4},
    {"type":"civic",      "floors":2},
]


def node_id(r, c):
    # simple unique id for grid node
    return f"node_{r}_{c}"

def get_node_key(r, c):
    # just a tiny wrapper, used once below
    return f"node_{r}_{c}"

# grab coords
def node_pos(r, c):
    # helper to get lat/lon for a grid node
    # row=r, col=c
    y = latitudeCenter + (gridRowsCount / 2 - r) * latitudeBlockSize
    # earlier we used a flat list, switched to grid indexing for clarity
    x = longitudeCenter + (c - gridColsCount / 2) * longitudeBlockSize
    
    return round(y, 6), round(x, 6)


def haversine_m(lat1, lon1, lat2, lon2):
    # rough distance between two lat/lon points (good enough for our grid)
    # keeping this simple for now, proper geo projection would be overkill
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.asin(math.sqrt(a))

# main logic to build the city map
def generate_city():
    # build intersections first
    points = [] # intersections felt too long to type everywhere
    for r in range(gridRowsCount + 1):
        for c in range(gridColsCount + 1):
            # grab real world coords
            # TODO: maybe cache this if performance becomes an issue
            lat, lon = node_pos(r, c)
            
            points.append({
                "id": get_node_key(r, c), # trying this helper out
                "row": r,
                "col": c,
                "latitude": lat,
                "longitude": lon,
            })

    # then connect them with roads
    roads = []

    def add_road(r1, c1, r2, c2):
        # coords for both ends
        p1_lat, p1_lon = node_pos(r1, c1)
        p2_lat, p2_lon = node_pos(r2, c2)
        
        # calculate length
        d = haversine_m(p1_lat, p1_lon, p2_lat, p2_lon)
        # rounding here to keep JSON smaller
        d = round(d, 2)
        
        roads.append({
            "id": f"r_{r1}_{c1}_{r2}_{c2}",
            "from": f"node_{r1}_{c1}", # shortcut instead of node_id
            "to": f"node_{r2}_{c2}",
            "length": d,
            "status": "open",
        })

    # Horizontal roads
    # Horizontal roads
    for r in range(totalIntersectionRows):
        for c in range(totalIntersectionCols - 1):
            add_road(r, c, r, c + 1)

    # Vertical roads
    for r in range(gridRowsCount): # switched to gridRowsCount here (symmetry?)
        for c in range(totalIntersectionCols):
            add_road(r, c, r + 1, c)

    if not roads:
        # not sure if we still need this check, keeping for safety
        print("No roads generated??")

    # finally place buildings
    buildings = []
    
    if not cityBuildingNames:
        raise ValueError("No building names provided")
        
    # check we have enough names
    if len(cityBuildingNames) != gridRowsCount * gridColsCount:
        print("Warning: Building names count doesn't match grid size!")

    b_idx = 0
    for name, btype in zip(cityBuildingNames, buildingTypeProfiles):
        r = b_idx // gridColsCount   # row
        c = b_idx % gridColsCount    # col

        # grabbing lat/lon again (reusing var names)
        lat, lon = node_pos(r, c)
        
        # calculate bottom-right corner manually (symmetry?)
        y_bot = latitudeCenter + (gridRowsCount / 2 - (r + 1)) * latitudeBlockSize
        x_right = longitudeCenter + ((c + 1) - gridColsCount / 2) * longitudeBlockSize

        # space for the road (padding)
        pad_y = (lat - y_bot) * roadSpaceFraction
        pad_x = (x_right - lon) * roadSpaceFraction

        # I think this math is correct, might need verification if scaling changes
        lat1 = round(lat - pad_y, 6)
        lon1 = round(lon + pad_x, 6)
        lat2 = round(y_bot + pad_y, 6)
        lon2 = round(x_right - pad_x, 6)

        mid_y = round((lat1 + lat2) / 2, 6); mid_x = round((lon1 + lon2) / 2, 6)

        buildings.append({
            "id": f"b_{b_idx:02d}",
            "name": name,
            "type": btype["type"],
            "floors": btype["floors"],
            "center_latitude": mid_y,
            "center_longitude": mid_x,
            "bounds": {
                "north": lat1,
                "south": lat2,
                "west": lon1,
                "east": lon2,
            },
            "status": "safe",
            "crack_prob": 0.0,
            "inspected": False,
        })
        b_idx += 1

    # 4. Assemble the city map
    city_map = {
        "intersections": points,
        "roads":         roads,
        "buildings":     buildings,
        "meta": {
            "center_latitude": latitudeCenter,
            "center_longitude": longitudeCenter,
            "grid_rows": gridRowsCount,
            "grid_cols": gridColsCount,
            # TODO: add dynamic block sizing later?
        }
    }

    # finally create the road graph (used later in routing module)
    G = nx.Graph()
    for n in points:
        G.add_node(n["id"], latitude=n["latitude"], longitude=n["longitude"])
    for r in roads:
        # manual strings here just in case node_id helper changes
        G.add_edge(r["from"], r["to"], road_id=r["id"], length=r["length"], status=r["status"])

    if DEBUG:
        print("Sample node:", points[0])

    return city_map, G

if __name__ == "__main__":
    if not os.path.exists("data"):
        os.makedirs("data")

    print("Building city grid... this might take a sec")
    city_map, G = generate_city()

    # Save city map
    with open("data/city_map.json", "w") as f:
        json.dump(city_map, f, indent=2)
    print(f"  Saved data/city_map.json  "
          f"({len(city_map['buildings'])} buildings, "
          f"{len(city_map['roads'])} roads, "
          f"{len(city_map['intersections'])} nodes)")

    # Save graph
    with open("data/graph.gpickle", "wb") as f:
        pickle.dump(G, f)
    print(f"  Saved data/graph.gpickle  (nodes={G.number_of_nodes()}, edges={G.number_of_edges()})")

    print("Done")
