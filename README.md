# Resilient City Simulation

>**Future Work:** This project is currently in development phase. Upcoming features include flood simulation and deploying reinforcement learning (RL) robots to autonomously inspect damaged buildings.

This is a little experimental "urban digital twin" I built to play around with disaster response logic. It's basically a 5×5 city grid where you can simulate earthquakes and see how they'd impact infrastructure and navigation in real-time.

The whole app runs locally with a FastAPI backend and a Leaflet.js map in the browser. I've keep it pretty minimalist, just the core simulation and a route planner that works around the damage.

## How to run it

You'll need **Python 3.9+** on your machine.

```bash
# 1. Install the code locally
git clone https://github.com/your-username/ResiliNav.git
cd ResiliNav

# 2. Set up a virtual environment (highly recommended)
python3 -m venv venv
source venv/bin/activate

# 3. Pull in the dependencies
pip install -r requirements.txt

# 4. Generate the map data
python scripts/city_builder.py

# 5. Launch the simulation
python app.py
```

Once it's running, just head over to **http://localhost:8000**. The city starts fresh every time you refresh the page.

## What's inside

- **The Simulator**: You can trigger earthquakes from magnitude 1 to 9. The app calculates damage based on proximity to the epicenter — buildings will turn orange (damaged) or red (evacuate) instantly. 
- **Smart Routing**: There's a built-in router that finds the fastest path between any two intersections. If an earthquake has blocked a road due to a nearby building collapse, the router will automatically pivot to find a safe alternative.
- **Interactive Map**: You can click on any building to see its name, type, and current health percentage.

**Built using:** FastAPI, Leaflet, and NetworkX.
