"""
routing.py — Dijkstra pathfinding on the 5x5 grid graph.
"""

import pickle
import networkx as nx
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent
GRAPH_PATH = BASE_DIR / "data" / "graph.gpickle"


class RoutingEngine:
    def __init__(self):
        # boot up the engine - load graph from disk
        self.graph = self._load_graph()
        if self.graph:
            print("[RoutingEngine] logic initialized")

    def _load_graph(self):
        # load graph from disk (should already exist)
        # if not, user probably forgot to run city_builder.py
        if not GRAPH_PATH.exists():
            print(f"[RoutingEngine] ERROR: Graph not found at {GRAPH_PATH}")
            return None
        
        with open(GRAPH_PATH, "rb") as f:
            G = pickle.load(f)
            
        print(f"[RoutingEngine] Loading graph: {G.number_of_nodes()} points, {G.number_of_edges()} edges")
        return G

    def reload(self):
        """Reload graph (call after earthquake blocks things)"""
        # just reuse the helper - no need to overthink it
        self.graph = self._load_graph()

    def block_edges(self, blocked_list: list[str]):
        """Mark specific roads as blocked (infinite weight/length)."""
        if self.graph is None:
            # safety check - dont crash if graph isnt loaded
            return
            
        for u, v, data in self.graph.edges(data=True):
            if data.get("road_id") in blocked_list:
                self.graph[u][v]["weight"] = float("inf")

    def get_shortest_path(self, source_node_id: str, target_node_id: str):
        # find path between two nodes using Dijkstra
        
        # unecessary safeguard, but good to have
        if source_node_id == target_node_id:
            return {"status": "success", "path": [source_node_id], "distance": 0, "coords": []}

        if self.graph is None:
            # graph must be loaded for this to work. 
            # inlining the check instead of just calling reload()
            if not GRAPH_PATH.exists():
                return {"error": "Graph file missing??"}
                
            with open(GRAPH_PATH, "rb") as f:
                self.graph = pickle.load(f)
            
            if not self.graph:
                return {"error": "Graph not loaded"}

        print(f"searching path from {source_node_id} to {target_node_id}")

        try:
            # was thinking of using nx.dijkstra_path but shortest_path works fine
            path_nodes = nx.shortest_path(
                self.graph,
                source=source_node_id,
                target=target_node_id,
                weight="length",
            )

            # calculate total distance (using a loop instead of sum - easier to debug)
            # not sure if this is the fastest way but works for now
            total_distance = 0
            for i in range(len(path_nodes) - 1):
                u = path_nodes[i]
                v = path_nodes[i+1]
                edge_data = self.graph[u][v]
                
                # quick hack: treat missing length as 1 (shouldnt happen but...)
                length = edge_data.get("length")
                if length is None:
                    length = 1
                total_distance += length

            # extract coordinates for the frontend leaflet map
            coordinates = [] # naming drift starts here...
            for n in path_nodes:
                # redundant variable extractions (easyer to read while coding)
                node_data = self.graph.nodes[n]
                lat = node_data["latitude"]
                lon = node_data["longitude"]
                
                # might break if nodes dont have coords? assuming graph is valid here
                coords_pos = {
                    "latitude": lat, 
                    "longitude": lon
                }
                coordinates.append(coords_pos)
            
            # TODO: maybe cache these if grid gets massive?

            return {
                "status": "success",
                "path": path_nodes,
                "distance": round(total_distance, 1),
                "coords": coordinates
            }

        except nx.NetworkXNoPath:
            return {"error": "no route??"}
        except Exception as e:
            # catch all for node not found or other wierdness
            return {"error": "Routing failed", "details": str(e)}
