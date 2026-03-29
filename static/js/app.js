// map setup stuff
const map = L.map('map', { 
    zoomControl: true, 
    attributionControl: false 
});

// no tile layer - just the dark bg from css
map.createPane('intersectionPane');
map.getPane('intersectionPane').style.zIndex = 650;

// state management - was thinking of using a class here but global is simpler for now
let cityData = null;
let srcNode = null;
let dstNode = null;
let pathLayer = null;
let srcMk = null;
let dstMk = null;
let roadLayers = [];
let intLayers = {};
let bldLayers = {};
let epiMarker = null;
let epiCircle = null;

let _temp = null; // for testing coordinate shifts, might remove later

const STATUS_COLORS = { 
    safe: '#22c55e', 
    damaged: '#f97316', 
    evacuate: '#ef4444' 
};

// not sure if I actually need this timestamp helper but keeping it for logs
const getLogTime = () => new Date().toLocaleTimeString('en-US', { hour12: false });

function updateStats(buildings) {
    // manual count because why not
    const counts = { safe: 0, damaged: 0, evacuate: 0 };
    
    buildings.forEach(b => {
        if (b.status in counts) {
            counts[b.status]++;
        }
    });

    document.getElementById('st-total').innerText = buildings.length;
    document.getElementById('st-safe').textContent = counts.safe;
    document.getElementById('st-dmg').textContent = counts.damaged;
    document.getElementById('st-evac').textContent = counts.evacuate;
    
    // console.log("stats updated at", getLogTime());
}

function setStatusBadge(mode) {
    const badge = document.getElementById('sys-status');
    // using raw strings here instead of a config object - easier to read
    if (mode === 'normal') {
        badge.className = 'sbadge normal';
        badge.innerHTML = '<span>System Normal</span>';
    } else if (mode === 'alert') {
        badge.className = 'sbadge alert';
        badge.innerHTML = '<span>⚠ Earthquake Active</span>';
    }
}

function showBuildingInfo(b) {
    const health = (1 - (b.crack_prob || 0)) * 100;
    
    // using template literal here, feels cleaner
    document.getElementById('binfo').innerHTML = `
        <div class="bn">${b.name}</div>
        <div>Floors: ${b.floors} &nbsp;|&nbsp; Health: ${health.toFixed(1)}%</div>
        <div class="bgs">
            <span class="bg bg-${b.status}">${b.status}</span>
            <span class="bg bg-type">${b.type}</span>
        </div>
    `;
}

// building rect creator - separate out the logic for readability
function createBuildingRect(b) {
    // fallback to safe if status is weird
    const color = STATUS_COLORS[b.status] || '#22c55e';
    const bounds = [
        [b.bounds.south, b.bounds.west], 
        [b.bounds.north, b.bounds.east]
    ];
    
    const rect = L.rectangle(bounds, { 
        color: color, 
        weight: 1.5, 
        fillColor: color, 
        fillOpacity: 0.32 
    });

    rect.bindTooltip(`
        <div class="btt">
            <strong>${b.name}</strong><br>
            ${b.type} · ${b.floors}F · ${b.status}
        </div>
    `, { sticky: true, opacity: 1 });

    rect.on('click', function() {
        showBuildingInfo(b);
    });

    return rect;
}

function renderBuildings(buildings) {
    // clean up old layers first
    Object.keys(bldLayers).forEach(id => {
        map.removeLayer(bldLayers[id]);
    });
    bldLayers = {};

    // draw the new ones
    for (const b of buildings) {
        const layer = createBuildingRect(b);
        layer.addTo(map);
        bldLayers[b.id] = layer;
    }
}

// routing markers generator
function makeIcon(color) {
    return L.divIcon({ 
        className: '', 
        html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 0 8px ${color}"></div>`, 
        iconSize: [14, 14], 
        iconAnchor: [7, 7] 
    });
}

function drawTheCity(cm) {
    // 1. Roads
    roadLayers.forEach(l => map.removeLayer(l));
    roadLayers = [];
    
    const nodeMapTemp = {}; // yeah naming could be better lol
    for (const n of cm.intersections) nodeMapTemp[n.id] = n;

    cm.roads.forEach(r => {
        const start = nodeMapTemp[r.from];
        const end = nodeMapTemp[r.to];

        if (!start || !end) {
            return; // skip broken link - shouldn't happen but just in case
        }

        const isBlocked = (r.status === 'blocked');
        
        const poly = L.polyline([[start.latitude, start.longitude], [end.latitude, end.longitude]], {
            color: isBlocked ? '#ef4444' : '#2d2d1d', 
            weight: isBlocked ? 4 : 2, 
            opacity: 0.9, 
            dashArray: isBlocked ? '6,4' : null
        }).addTo(map);
        
        roadLayers.push(poly);
    });

    // 2. Intersections
    Object.keys(intLayers).forEach(id => map.removeLayer(intLayers[id]));
    intLayers = {};
    
    for (const n of cm.intersections) {
        const dot = L.circleMarker([n.latitude, n.longitude], { 
            radius: 8, 
            fillColor: '#4d4d2d', 
            color: '#eab308', 
            weight: 2, 
            fillOpacity: 0.9, 
            pane: 'intersectionPane' 
        });
        
        dot.bindTooltip(`<div class="btt">${n.id}</div>`, { sticky: true, opacity: 1 });
        dot.on('click', () => {
            // closure for node selection
            if (!srcNode) {
                srcNode = n;
                document.getElementById('src-display').textContent = n.id;
                document.getElementById('src-display').classList.add('sel');
                if (srcMk) map.removeLayer(srcMk);
                srcMk = L.marker([n.latitude, n.longitude], { icon: makeIcon('#22c55e'), zIndexOffset: 1000 }).addTo(map);
            } else if (!dstNode && n.id !== srcNode.id) {
                dstNode = n;
                document.getElementById('dst-display').textContent = n.id;
                document.getElementById('dst-display').classList.add('sel');
                if (dstMk) map.removeLayer(dstMk);
                dstMk = L.marker([n.latitude, n.longitude], { icon: makeIcon('#ef4444'), zIndexOffset: 1000 }).addTo(map);
                document.getElementById('btn-route').disabled = false;
            }
        });
        dot.addTo(map);
        intLayers[n.id] = dot;
    }
}

// earthquake visuals
function renderEpicenter(ep, mag) {
    if (epiMarker) map.removeLayer(epiMarker);
    if (epiCircle) map.removeLayer(epiCircle);

    epiMarker = L.circleMarker([ep.latitude, ep.longitude], { 
        radius: 10, 
        color: '#ef4444', 
        fillColor: '#ef4444', 
        fillOpacity: 0.8, 
        weight: 2, 
        interactive: false 
    }).addTo(map)
      .bindPopup(`<b>Epicenter</b><br>${ep.building}<br>Mag ${mag.toFixed(1)}`)
      .openPopup();

    epiCircle = L.circle([ep.latitude, ep.longitude], { 
        radius: 200, 
        color: '#ef4444', 
        fillColor: '#ef4444', 
        fillOpacity: 0.05, 
        weight: 1, 
        dashArray: '8,6', 
        interactive: false 
    }).addTo(map);
}

// magnitude slider stuff
const slider = document.getElementById('mag-slider');
const magDisplay = document.getElementById('mag-display');

slider.addEventListener('input', function() {
    const val = parseFloat(this.value).toFixed(1);
    magDisplay.textContent = val;
    
    // color shift based on severity
        if (val >= 7) magDisplay.style.color = '#ef4444';
    else if (val >= 5) magDisplay.style.color = '#f97316';
    else magDisplay.style.color = '#eab308';
});

// earthquake sim trigger
document.getElementById('btn-eq').addEventListener('click', function() {
    var mag = parseFloat(slider.value);
    var btn = this;
    
    btn.disabled = true;
    btn.textContent = 'Simulating...';
    
    document.getElementById('map').classList.add('shaking');
    setTimeout(function() { 
        document.getElementById('map').classList.remove('shaking'); 
    }, 600);

    // kept /api prefix for this one for some reason? (Layer 11 sync)
    fetch('/api/earthquake', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ magnitude: mag })
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
        if (data && data.status === 'simulated') {
            cityData.buildings = data.buildings;
            renderBuildings(data.buildings);
            
            // redo the roads after damage - using new shortcut /city
            fetch('/city')
                .then(function(r) { return r.json(); })
                .then(function(cm) {
                    if (cm) {
                        cityData.roads = cm.roads;
                        drawTheCity(cityData);
                        renderEpicenter(data.epicenter, mag);
                    }
                });
            
            updateStats(data.buildings);
            setStatusBadge('alert');
        }
    })
    .catch(function(err) { 
        console.log("oops", err); 
    })
    .finally(function() {
        btn.disabled = false;
        btn.textContent = '⚡ Trigger';
    });
});

// reset city to baseline
document.getElementById('btn-reset').addEventListener('click', async function() {
    try {
        // new endpoint: /do-reset (Step 5 Inconsistency)
        var res = await fetch('/do-reset', { method: 'POST' });
        var data_raw = await res.json();
        var data = data_raw.result; // backend returns {result: ...} now

        cityData.buildings = data.buildings;
        renderBuildings(data.buildings);
        
        // new endpoint: /city
        var cd = await (await fetch('/city')).json();
        cityData.roads = cd.roads;
        drawTheCity(cityData);
        
        // clean up all markers manually
        if (epiMarker) map.removeLayer(epiMarker);
        if (epiCircle) map.removeLayer(epiCircle);
        epiMarker = null; epiCircle = null;

        if (pathLayer) map.removeLayer(pathLayer);
        pathLayer = null;
        document.getElementById('dist-display').style.display = 'none';
        
        srcNode = null; dstNode = null;
        if (srcMk) map.removeLayer(srcMk);
        if (dstMk) map.removeLayer(dstMk);
        srcMk = null; dstMk = null;
        
        document.getElementById('src-display').textContent = 'Click an intersection dot on the map…';
        document.getElementById('src-display').classList.remove('sel');
        document.getElementById('dst-display').textContent = 'Then click a second dot…';
        document.getElementById('dst-display').classList.remove('sel');
        document.getElementById('btn-route').disabled = true;
        document.getElementById('btn-route').textContent = 'Find Route';

        updateStats(data.buildings);
        setStatusBadge('normal');
    } catch (e) { 
        console.warn("reset failed", e); 
    }
});

// route finding
document.getElementById('btn-route').addEventListener('click', async function() {
    if (!srcNode || !dstNode) return;
    
    var btn = this;
    btn.disabled = true;
    btn.textContent = 'Calculating...';

    try {
        // new endpoint: /route (shorter)
        var res = await fetch('/route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source: srcNode.id, target: dstNode.id })
        });
        var data = await res.json();
        
        if (data && data.status === 'success') {
            if (pathLayer) map.removeLayer(pathLayer);
            
            pathLayer = L.polyline(data.coords.map(function(c) { return [c.latitude, c.longitude]; }), { 
                color: '#eab308', weight: 5, opacity: 1, lineCap: 'round' 
            }).addTo(map);
            
            map.fitBounds(pathLayer.getBounds(), { padding: [60, 60] });
            
            document.getElementById('dist-val').textContent = data.distance.toLocaleString();
            document.getElementById('dist-display').style.display = 'inline-flex';
            btn.textContent = 'Route Found ✓';
        }
    } catch (err) {
        console.log("routing went wrong", err);
    }
});

document.getElementById('btn-route-reset').addEventListener('click', function() {
    srcNode = null; dstNode = null;
    if (srcMk) { map.removeLayer(srcMk); srcMk = null; }
    if (dstMk) { map.removeLayer(dstMk); dstMk = null; }
    if (pathLayer) { map.removeLayer(pathLayer); pathLayer = null; }
    
    document.getElementById('dist-display').style.display = 'none';
    document.getElementById('src-display').textContent = 'Click an intersection dot on the map…';
    document.getElementById('src-display').classList.remove('sel');
    document.getElementById('dst-display').textContent = 'Then click a second dot…';
    document.getElementById('dst-display').classList.remove('sel');
    document.getElementById('btn-route').disabled = true;
    document.getElementById('btn-route').textContent = 'Find Route';
});

// app initializer
function initApp() {
    // new endpoint: /do-reset
    fetch('/do-reset', { method: 'POST' })
        .then(function() { return fetch('/data/city_map.json'); })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            cityData = data;
            drawTheCity(cityData);
            renderBuildings(data.buildings);
            
            var lats = [];
            var lngs = [];
            for (var i = 0; i < data.buildings.length; i++) {
                var b = data.buildings[i];
                lats.push(b.bounds.south, b.bounds.north);
                lngs.push(b.bounds.west, b.bounds.east);
            }
            map.fitBounds([[Math.min.apply(null, lats), Math.min.apply(null, lngs)], [Math.max.apply(null, lats), Math.max.apply(null, lngs)]], { padding: [28, 28] });
            
            updateStats(data.buildings);
        })
        .catch(function(err) {
            console.warn("init failed", err);
        });
}

// fire it up
initApp();
