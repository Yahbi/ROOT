/**
 * Neural Galaxy — Sacred Metatron Brain
 *
 * Metatron's Cube is the skeleton. Agents live on and around its vertices
 * in full 3D space. Every connection is a curved, pulsing neuron dendrite.
 * The whole structure breathes, vibrates, and fires neural signals.
 * Each agent has its own unique color. Click any agent for details.
 *
 * Uses Three.js for WebGL rendering.
 */

const NeuralGalaxy = (() => {
    // ── State ──────────────────────────────────────────────────
    let scene, camera, renderer, controls;
    let nodes = [], edges = [], divisions = [];
    let nodeObjects = new Map();
    let edgeObjects = [];
    let labelSprites = new Map();
    let sacredGroup;
    let clock, animationId;
    let hoveredNode = null;
    let selectedNode = null;
    let container = null;
    let tooltip = null;
    let infoPanel = null;
    let isInitialized = false;
    let pulseQueue = [];
    let nebulaParticles = null;
    let neuralSignals = [];
    let signalTimer = 0;
    let agentColorMap = new Map();
    let metatronLines = [];

    // ── Color generation ─────────────────────────────────────
    function _genColor(i) {
        const h = (i * 137.508) % 360;
        const s = 70 + (i % 3) * 10;
        const l = 55 + (i % 4) * 5;
        return _hsl2hex(h, s, l);
    }
    function _hsl2hex(h, s, l) {
        s /= 100; l /= 100;
        const k = n => (n + h / 30) % 12;
        const a = s * Math.min(l, 1 - l);
        const f = n => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
        return (Math.round(f(0)*255) << 16) | (Math.round(f(8)*255) << 8) | Math.round(f(4)*255);
    }
    function _css(hex) { return '#' + hex.toString(16).padStart(6, '0'); }

    const ACTIVITY_VERBS = [
        'Analyzing patterns', 'Scanning signals', 'Processing data',
        'Learning from history', 'Optimizing routes', 'Monitoring health',
        'Evaluating risks', 'Researching insights', 'Building knowledge',
        'Coordinating tasks', 'Executing directives', 'Reviewing outcomes',
        'Synthesizing memory', 'Predicting trends', 'Generating strategies',
    ];

    // ── Metatron's Cube — 13 vertices in full 3D ─────────────
    function _metatronVerts(R) {
        const pts = [];
        const r1 = R * 0.42;
        const r2 = R * 0.84;

        // 0: center
        pts.push(new THREE.Vector3(0, 0, 0));

        // 1-6: inner hexagon with 3D elevation
        for (let i = 0; i < 6; i++) {
            const a = (Math.PI / 3) * i;
            const elev = (i % 2 === 0 ? 1 : -1) * r1 * 0.45;
            pts.push(new THREE.Vector3(
                r1 * Math.cos(a),
                elev,
                r1 * Math.sin(a)
            ));
        }

        // 7-12: outer hexagon, offset in 3D
        for (let i = 0; i < 6; i++) {
            const a = (Math.PI / 3) * i + Math.PI / 6;
            const elev = (i % 2 === 0 ? -1 : 1) * r2 * 0.3;
            pts.push(new THREE.Vector3(
                r2 * Math.cos(a),
                elev,
                r2 * Math.sin(a)
            ));
        }
        return pts;
    }

    const SACRED_R = 130;

    // ── Init ─────────────────────────────────────────────────
    function init(containerId) {
        container = document.getElementById(containerId);
        if (!container || isInitialized) return;

        // Ensure container has dimensions (panel may have just become visible)
        let W = container.clientWidth, H = container.clientHeight;
        if (W < 100) W = container.parentElement?.clientWidth || window.innerWidth - 260;
        if (H < 100) H = container.parentElement?.clientHeight || window.innerHeight - 50;

        scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x040410, 0.00035);

        camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 5000);
        camera.position.set(0, 120, 320);
        camera.lookAt(0, 0, 0);

        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(W, H);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setClearColor(0x040410, 1);
        container.appendChild(renderer.domElement);

        controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.06;
        controls.rotateSpeed = 0.3;
        controls.zoomSpeed = 0.5;
        controls.minDistance = 40;
        controls.maxDistance = 2000;
        controls.autoRotate = true;
        controls.autoRotateSpeed = 0.07;

        scene.add(new THREE.AmbientLight(0x1a1a3a, 0.5));
        const l1 = new THREE.PointLight(0xFFD700, 1.5, 700); l1.position.set(0, 130, 0); scene.add(l1);
        const l2 = new THREE.PointLight(0x7B68EE, 0.7, 600); l2.position.set(-160, -70, 160); scene.add(l2);
        const l3 = new THREE.PointLight(0xFF3399, 0.4, 500); l3.position.set(160, 70, -160); scene.add(l3);
        const l4 = new THREE.PointLight(0x00FFCC, 0.35, 400); l4.position.set(0, -110, 0); scene.add(l4);

        clock = new THREE.Clock();

        tooltip = document.createElement('div');
        tooltip.className = 'neural-tooltip';
        tooltip.style.display = 'none';
        container.appendChild(tooltip);

        infoPanel = document.createElement('div');
        infoPanel.className = 'neural-info-banner';
        infoPanel.style.display = 'none';
        container.appendChild(infoPanel);

        _createStarfield();
        _createNebulaParticles();

        window.addEventListener('resize', _onResize);
        renderer.domElement.addEventListener('mousemove', _onMouseMove);
        renderer.domElement.addEventListener('click', _onClick);

        isInitialized = true;
        _fetchAndBuild();
        _animate();
        // Force resize after everything renders to fix dimension issues
        setTimeout(_onResize, 300);
        setTimeout(_onResize, 1000);
    }

    function destroy() {
        if (animationId) { cancelAnimationFrame(animationId); animationId = null; }
        window.removeEventListener('resize', _onResize);
        if (renderer && renderer.domElement) {
            renderer.domElement.removeEventListener('mousemove', _onMouseMove);
            renderer.domElement.removeEventListener('click', _onClick);
        }

        // Dispose Three.js geometries and materials
        if (scene) {
            scene.traverse(obj => {
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) {
                    if (Array.isArray(obj.material)) {
                        obj.material.forEach(m => m.dispose());
                    } else {
                        obj.material.dispose();
                    }
                }
            });
        }

        if (controls) { controls.dispose(); controls = null; }
        if (renderer) { renderer.dispose(); renderer.domElement.remove(); renderer = null; }
        if (tooltip) { tooltip.remove(); tooltip = null; }
        if (infoPanel) { infoPanel.remove(); infoPanel = null; }
        nodeObjects.clear(); edgeObjects = []; labelSprites.clear();
        agentColorMap.clear(); metatronLines = [];
        neuralSignals.forEach(s => { if (scene) scene.remove(s.mesh); });
        neuralSignals = []; signalTimer = 0;
        scene = null; camera = null; container = null;
        isInitialized = false;
    }

    // ── Data ─────────────────────────────────────────────────
    async function _fetchAndBuild() {
        try {
            const h = {}; if (window._apiKey) h['X-API-Key'] = window._apiKey;
            const resp = await fetch('/api/network/graph', { headers: h });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            nodes = data.nodes || []; edges = data.edges || []; divisions = data.divisions || [];
            _assignColors();
            _buildScene();
            _updateStats(data.stats || {});
            _updateLegend();
            _pollActivity();
        } catch (err) {
            console.error('Neural Galaxy:', err);
            _showFallback();
        }
    }

    function _assignColors() {
        nodes.forEach((a, i) => agentColorMap.set(a.id, _genColor(i)));
        window._neuralAgentColors = {};
        agentColorMap.forEach((c, id) => { window._neuralAgentColors[id] = _css(c); });
    }

    // ── Build full scene ─────────────────────────────────────
    function _buildScene() {
        const verts = _metatronVerts(SACRED_R);

        // Sacred geometry group (rotates slowly)
        sacredGroup = new THREE.Group();
        _buildMetatronWireframe(verts, sacredGroup);
        _buildFlowerOfLife(sacredGroup);
        _buildSacredRings(sacredGroup);
        scene.add(sacredGroup);

        // Place agents
        _placeAgents(verts);

        // Build visible dendrite connections between ALL agents
        _buildDendrites();
    }

    // ── Metatron wireframe ───────────────────────────────────
    function _buildMetatronWireframe(verts, group) {
        const mat = new THREE.LineBasicMaterial({
            color: 0xFFD700, transparent: true, opacity: 0.045,
            blending: THREE.AdditiveBlending,
        });
        for (let i = 0; i < verts.length; i++) {
            for (let j = i + 1; j < verts.length; j++) {
                const geo = new THREE.BufferGeometry().setFromPoints([verts[i], verts[j]]);
                const line = new THREE.Line(geo, mat.clone());
                line.userData = { phase: Math.random() * 6.28, base: 0.045 };
                group.add(line);
                metatronLines.push(line);
            }
        }

        // Circles at each vertex
        verts.forEach((pt, i) => {
            const cGeo = new THREE.RingGeometry(3, 3.4, 48);
            const cMat = new THREE.MeshBasicMaterial({
                color: i === 0 ? 0xFFD700 : 0x7B68EE,
                transparent: true, opacity: 0.08, side: THREE.DoubleSide,
                blending: THREE.AdditiveBlending,
            });
            const c = new THREE.Mesh(cGeo, cMat);
            c.position.copy(pt);
            c.lookAt(0, 0, 0);
            group.add(c);
        });
    }

    function _buildFlowerOfLife(group) {
        const r = SACRED_R * 0.14;
        const mat = new THREE.LineBasicMaterial({
            color: 0x4ECDC4, transparent: true, opacity: 0.025,
            blending: THREE.AdditiveBlending,
        });
        const centers = [new THREE.Vector3(0, 0, 0)];
        for (let i = 0; i < 6; i++) {
            const a = (Math.PI / 3) * i;
            centers.push(new THREE.Vector3(r * Math.cos(a), r * Math.sin(a), 0));
        }
        for (let i = 0; i < 12; i++) {
            const a = (Math.PI / 6) * i;
            centers.push(new THREE.Vector3(r * 2 * Math.cos(a), r * 2 * Math.sin(a), 0));
        }
        centers.forEach(c => {
            const pts = [];
            for (let j = 0; j <= 64; j++) {
                const a = (j / 64) * Math.PI * 2;
                pts.push(new THREE.Vector3(c.x + r * Math.cos(a), c.y + r * Math.sin(a), c.z));
            }
            group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
        });
    }

    function _buildSacredRings(group) {
        const rr = SACRED_R * 1.15;
        const mat = new THREE.LineBasicMaterial({
            color: 0x7B68EE, transparent: true, opacity: 0.02,
            blending: THREE.AdditiveBlending,
        });
        [{x:0,y:0,z:0},{x:1.05,y:0.52,z:0},{x:0,y:1.05,z:0.52}].forEach(rot => {
            const pts = [];
            for (let i = 0; i <= 128; i++) {
                const a = (i / 128) * Math.PI * 2;
                pts.push(new THREE.Vector3(rr * Math.cos(a), rr * Math.sin(a), 0));
            }
            const ring = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat.clone());
            ring.rotation.set(rot.x, rot.y, rot.z);
            group.add(ring);
        });
    }

    // ── Place agents on Metatron vertices ─────────────────────
    function _placeAgents(verts) {
        const core = nodes.filter(n => n.division === 'core');
        const other = nodes.filter(n => n.division !== 'core');

        // Assign to 13 vertices
        const slots = new Map();
        for (let i = 0; i < 13; i++) slots.set(i, []);

        core.forEach((a, i) => slots.get(i % 13).push(a));

        const divKeys = [...new Set(other.map(a => a.division))];
        const divSlot = {};
        divKeys.forEach((d, i) => { divSlot[d] = 7 + (i % 6); });
        other.forEach(a => {
            slots.get(divSlot[a.division] || (7 + Math.floor(Math.random() * 6))).push(a);
        });

        slots.forEach((agents, vi) => {
            const base = verts[vi];
            agents.forEach((agent, idx) => {
                const color = agentColorMap.get(agent.id) || 0xAAAAAA;
                const isCore = agent.division === 'core';
                const size = isCore ? 2.6 : 0.9 + (agent.activity_level || 0.3) * 0.7;

                // Position: first on vertex, rest scattered in 3D shell around it
                let pos;
                if (idx === 0) {
                    pos = base.clone();
                } else {
                    const phi = Math.acos(1 - 2 * ((idx * 0.618) % 1));
                    const theta = idx * 2.399 + vi;
                    const spread = 8 + idx * 1.8;
                    pos = new THREE.Vector3(
                        base.x + Math.sin(phi) * Math.cos(theta) * spread,
                        base.y + Math.cos(phi) * spread * 0.7,
                        base.z + Math.sin(phi) * Math.sin(theta) * spread
                    );
                }

                const geo = new THREE.SphereGeometry(size, isCore ? 28 : 12, isCore ? 28 : 12);
                const mat = new THREE.MeshPhongMaterial({
                    color, emissive: color,
                    emissiveIntensity: isCore ? 0.65 : 0.3,
                    transparent: true, opacity: isCore ? 0.95 : 0.85,
                    shininess: 100,
                });
                const mesh = new THREE.Mesh(geo, mat);
                mesh.position.copy(pos);
                mesh.userData = {
                    ...agent, baseSize: size,
                    baseEmissive: isCore ? 0.65 : 0.3,
                    agentColor: color,
                    vPhase: Math.random() * 6.28,
                    vFreq: 1.2 + Math.random() * 1.8,
                    vAmp: isCore ? 0.35 : 0.18,
                    pFreq: 0.6 + Math.random() * 0.8,
                    basePos: pos.clone(),
                    activityVerb: ACTIVITY_VERBS[Math.floor(Math.random() * ACTIVITY_VERBS.length)],
                };
                scene.add(mesh);
                nodeObjects.set(agent.id, mesh);

                // Glow halos
                for (let g = 0; g < (isCore ? 3 : 2); g++) {
                    const gGeo = new THREE.SphereGeometry(size * (1.8 + g * 1.6), 8, 8);
                    const gMat = new THREE.MeshBasicMaterial({
                        color, transparent: true,
                        opacity: (isCore ? 0.07 : 0.035) / (g + 1),
                        side: THREE.BackSide,
                        blending: THREE.AdditiveBlending, depthWrite: false,
                    });
                    mesh.add(new THREE.Mesh(gGeo, gMat));
                }

                // Label
                if (isCore) {
                    const label = _createLabel(agent.name || agent.id, color);
                    label.position.set(pos.x, pos.y + size + 5, pos.z);
                    scene.add(label);
                    labelSprites.set(agent.id, label);
                }
            });
        });
    }

    // ── Dendrite connections — curved, organic, pulsing ───────
    function _buildDendrites() {
        const allIds = Array.from(nodeObjects.keys());
        const seen = new Set();
        const pk = (a, b) => a < b ? a + '|' + b : b + '|' + a;

        const addCurve = (srcId, tgtId, baseOp) => {
            const key = pk(srcId, tgtId);
            if (seen.has(key)) return;
            seen.add(key);

            const sM = nodeObjects.get(srcId), tM = nodeObjects.get(tgtId);
            if (!sM || !tM) return;
            const sP = sM.position, tP = tM.position;
            const d = sP.distanceTo(tP);
            if (d < 0.5) return;

            // Curved control point
            const mid = new THREE.Vector3().addVectors(sP, tP).multiplyScalar(0.5);
            const dir = new THREE.Vector3().subVectors(tP, sP).normalize();
            const perp = new THREE.Vector3();
            if (Math.abs(dir.y) < 0.9) perp.crossVectors(dir, new THREE.Vector3(0, 1, 0)).normalize();
            else perp.crossVectors(dir, new THREE.Vector3(1, 0, 0)).normalize();
            const p2 = new THREE.Vector3().crossVectors(dir, perp).normalize();
            const cm = d * (0.1 + Math.random() * 0.22);
            const wa = Math.random() * 6.28;
            const cp = mid.clone()
                .add(perp.clone().multiplyScalar(Math.cos(wa) * cm))
                .add(p2.clone().multiplyScalar(Math.sin(wa) * cm));

            const curve = new THREE.QuadraticBezierCurve3(sP.clone(), cp, tP.clone());
            const geo = new THREE.BufferGeometry().setFromPoints(curve.getPoints(24));
            const color = sM.userData.agentColor || 0xFFD700;
            const mat = new THREE.LineBasicMaterial({
                color, transparent: true, opacity: baseOp,
                blending: THREE.AdditiveBlending, depthWrite: false,
            });
            const line = new THREE.Line(geo, mat);
            line.userData = {
                source: srcId, target: tgtId,
                baseOp, color,
                phase: Math.random() * 6.28,
                pFreq: 0.3 + Math.random() * 1.0,
            };
            scene.add(line);
            edgeObjects.push(line);
        };

        // API edges (brighter)
        edges.forEach(e => addCurve(e.source, e.target, e.type === 'core' ? 0.14 : 0.065));

        // Same-division connections (moderate)
        const byDiv = {};
        allIds.forEach(id => {
            const d = nodeObjects.get(id).userData.division || 'x';
            if (!byDiv[d]) byDiv[d] = [];
            byDiv[d].push(id);
        });
        Object.values(byDiv).forEach(ids => {
            for (let i = 0; i < ids.length; i++) {
                for (let j = i + 1; j < ids.length; j++) {
                    addCurve(ids[i], ids[j], 0.035);
                }
            }
        });

        // Cross-division (faint, capped)
        let cross = 0;
        const maxCross = 800;
        for (let i = 0; i < allIds.length && cross < maxCross; i++) {
            for (let j = i + 1; j < allIds.length && cross < maxCross; j++) {
                if (seen.has(pk(allIds[i], allIds[j]))) continue;
                const dA = nodeObjects.get(allIds[i]).userData.division;
                const dB = nodeObjects.get(allIds[j]).userData.division;
                if (dA === dB) continue;
                const dist = nodeObjects.get(allIds[i]).position.distanceTo(nodeObjects.get(allIds[j]).position);
                if (Math.random() > Math.max(0.02, 1 - dist / 280)) continue;
                addCurve(allIds[i], allIds[j], 0.012);
                cross++;
            }
        }
    }

    // ── Neural signals — travel along existing dendrites ─────
    function _findEdge(srcId, tgtId) {
        return edgeObjects.find(l => {
            const u = l.userData;
            return (u.source === srcId && u.target === tgtId) ||
                   (u.source === tgtId && u.target === srcId);
        });
    }

    function _fireSignal(srcId, tgtId, color) {
        const sM = nodeObjects.get(srcId), tM = nodeObjects.get(tgtId);
        if (!sM || !tM) return;
        const sP = sM.position.clone(), tP = tM.position.clone();
        const d = sP.distanceTo(tP);
        if (d < 2) return;

        // Find the matching edge to light up
        const edge = _findEdge(srcId, tgtId);

        // Build curve — reuse edge geometry direction or make one
        const mid = new THREE.Vector3().addVectors(sP, tP).multiplyScalar(0.5);
        const dir = new THREE.Vector3().subVectors(tP, sP).normalize();
        const perp = new THREE.Vector3();
        if (Math.abs(dir.y) < 0.9) perp.crossVectors(dir, new THREE.Vector3(0, 1, 0)).normalize();
        else perp.crossVectors(dir, new THREE.Vector3(1, 0, 0)).normalize();
        const cp = mid.clone().add(perp.multiplyScalar(d * 0.13));
        const curve = new THREE.QuadraticBezierCurve3(sP, cp, tP);

        const c = color || 0xFFD700;
        const geo = new THREE.SphereGeometry(0.7, 8, 8);
        const mat = new THREE.MeshBasicMaterial({
            color: c, transparent: true, opacity: 0.9,
            blending: THREE.AdditiveBlending, depthWrite: false,
        });
        const sig = new THREE.Mesh(geo, mat);
        sig.position.copy(sP);

        // Trail
        const tGeo = new THREE.SphereGeometry(2.5, 6, 6);
        const tMat = new THREE.MeshBasicMaterial({
            color: c, transparent: true, opacity: 0.08,
            blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.BackSide,
        });
        sig.add(new THREE.Mesh(tGeo, tMat));
        scene.add(sig);

        // Flash source node on fire
        _flashNode(srcId);

        neuralSignals.push({
            mesh: sig, curve, progress: 0,
            speed: 0.5 + Math.random() * 0.6,  // faster travel for denser signal flow
            edge,                  // linked dendrite line (may be null)
            srcId, tgtId, color: c,
        });
    }

    function _flashNode(id) {
        const m = nodeObjects.get(id);
        if (!m) return;
        pulseQueue.push({ mesh: m, t0: clock.getElapsedTime(), dur: 0.6 });
    }

    // ── Organic Activity System ─────────────────────────────────
    // Every agent is ALWAYS working. Signals flow constantly between agents
    // representing real autonomous activity: learning, researching, trading,
    // monitoring, collaborating, planning, executing.

    const _ORGANIC_PATTERNS = [
        // ASTRA routing cycle — constantly dispatching work
        { from: 'astra', targets: ['researcher','analyst','swarm','miro','coder','writer','guardian','builder'], weight: 5 },
        // Learning chain — agents teaching each other
        { from: 'researcher', targets: ['analyst','miro','astra'], weight: 3 },
        { from: 'analyst', targets: ['swarm','researcher','astra'], weight: 3 },
        // Trading intelligence chain — market data flows
        { from: 'swarm', targets: ['analyst','miro','astra'], weight: 4 },
        { from: 'miro', targets: ['swarm','analyst','astra'], weight: 3 },
        // Builder self-improvement cycle
        { from: 'builder', targets: ['coder','researcher','astra'], weight: 2 },
        { from: 'coder', targets: ['builder','analyst','astra'], weight: 2 },
        // Guardian monitoring everything
        { from: 'guardian', targets: ['astra','researcher','analyst','swarm'], weight: 2 },
        // Writer reporting findings
        { from: 'writer', targets: ['astra','researcher','analyst'], weight: 1 },
        // Cross-division collaboration (civilization agents)
        { from: 'researcher', targets: ['coder','writer','guardian'], weight: 2 },
        { from: 'miro', targets: ['researcher','guardian','swarm'], weight: 2 },
    ];

    let _organicTimer = 0;
    let _burstTimer = 0;
    let _activityLevel = 1.0; // increases with real WebSocket events

    function _autoFire() {
        const ids = Array.from(nodeObjects.keys());
        if (ids.length < 2) return;

        // Scale signals based on activity level (more real events = more organic activity)
        const baseSignals = 6 + Math.floor(Math.random() * 5); // 6-10 base signals per tick
        const n = Math.min(Math.floor(baseSignals * _activityLevel), 18);

        // 70% pattern-based (organic), 30% random (representing background work)
        const patternCount = Math.ceil(n * 0.7);
        const randomCount = n - patternCount;

        // Pattern-based signals (follow real agent communication patterns)
        for (let i = 0; i < patternCount; i++) {
            const pattern = _ORGANIC_PATTERNS[Math.floor(Math.random() * _ORGANIC_PATTERNS.length)];
            const srcId = pattern.from;
            const tgtId = pattern.targets[Math.floor(Math.random() * pattern.targets.length)];
            if (nodeObjects.has(srcId) && nodeObjects.has(tgtId)) {
                const c = nodeObjects.get(srcId)?.userData.agentColor || 0xFFD700;
                // Stagger signals slightly for organic feel
                setTimeout(() => _fireSignal(srcId, tgtId, c), Math.random() * 400);
            }
        }

        // Random signals (civilization agents working in background)
        for (let i = 0; i < randomCount; i++) {
            const si = Math.floor(Math.random() * ids.length);
            let ti = Math.floor(Math.random() * ids.length);
            if (si === ti) ti = (ti + 1) % ids.length;
            const c = nodeObjects.get(ids[si])?.userData.agentColor || 0xFFD700;
            setTimeout(() => _fireSignal(ids[si], ids[ti], c), Math.random() * 600);
        }

        // Activity level slowly decays toward baseline but never below 1.0
        _activityLevel = Math.max(1.0, _activityLevel * 0.98);
    }

    // Boost activity when real WebSocket events arrive
    function _boostActivity() {
        _activityLevel = Math.min(_activityLevel + 0.3, 3.0);
    }

    function _updateSignals() {
        neuralSignals = neuralSignals.filter(s => {
            s.progress += s.speed * 0.016;
            if (s.progress >= 1) {
                scene.remove(s.mesh); s.mesh.geometry.dispose(); s.mesh.material.dispose();
                // Flash target node on arrival
                _flashNode(s.tgtId);
                // Mark edge for fade-out (will decay in _animate)
                if (s.edge) {
                    s.edge.userData.fireProgress = -1; // signal: start fading
                    s.edge.userData.fireFade = 1.0;
                    s.edge.userData.fireColor = s.color;
                }
                return false;
            }
            s.mesh.position.copy(s.curve.getPoint(s.progress));
            const f = Math.sin(s.progress * Math.PI);
            s.mesh.material.opacity = 0.9 * f;
            s.mesh.scale.setScalar(0.4 + f * 0.8);

            // ── Progressive dendrite light-up ──
            if (s.edge) {
                s.edge.userData.fireProgress = s.progress;
                s.edge.userData.fireColor = s.color;
                // Boost edge opacity & color where the signal has passed
                const peakOp = Math.min(s.edge.userData.baseOp * 12, 0.65);
                s.edge.material.opacity = peakOp;
                s.edge.material.color.setHex(s.color);
            }
            return true;
        });
    }

    // ── Environment ──────────────────────────────────────────
    function _createNebulaParticles() {
        const n = 2500;
        const geo = new THREE.BufferGeometry();
        const pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
        for (let i = 0; i < n; i++) {
            const r = 280 * Math.pow(Math.random(), 0.5);
            const t = Math.random() * 6.28, p = Math.acos(2 * Math.random() - 1);
            pos[i*3] = r*Math.sin(p)*Math.cos(t);
            pos[i*3+1] = r*Math.sin(p)*Math.sin(t)*0.5;
            pos[i*3+2] = r*Math.cos(p);
            const c = Math.random();
            if (c<.25){col[i*3]=1;col[i*3+1]=.84;col[i*3+2]=0;}
            else if(c<.45){col[i*3]=.48;col[i*3+1]=.41;col[i*3+2]=.93;}
            else if(c<.65){col[i*3]=.3;col[i*3+1]=.75;col[i*3+2]=.7;}
            else{col[i*3]=.2;col[i*3+1]=.25;col[i*3+2]=.45;}
        }
        geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
        nebulaParticles = new THREE.Points(geo, new THREE.PointsMaterial({
            size: .6, vertexColors: true, transparent: true, opacity: .22,
            sizeAttenuation: true, blending: THREE.AdditiveBlending, depthWrite: false,
        }));
        scene.add(nebulaParticles);
    }

    function _createStarfield() {
        const n = 5000;
        const geo = new THREE.BufferGeometry();
        const pos = new Float32Array(n*3), col = new Float32Array(n*3);
        for (let i = 0; i < n; i++) {
            pos[i*3]=(Math.random()-.5)*4000;
            pos[i*3+1]=(Math.random()-.5)*4000;
            pos[i*3+2]=(Math.random()-.5)*4000;
            const w=Math.random();
            col[i*3]=.6+w*.4;col[i*3+1]=.6+w*.2;col[i*3+2]=.7+(1-w)*.3;
        }
        geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
        scene.add(new THREE.Points(geo, new THREE.PointsMaterial({
            size: .3, vertexColors: true, transparent: true, opacity: .4, sizeAttenuation: true,
        })));
    }

    function _createLabel(text, color) {
        const c = document.createElement('canvas');
        c.width = 256; c.height = 64;
        const x = c.getContext('2d');
        const h = _css(color);
        x.shadowColor = h; x.shadowBlur = 10;
        x.font = 'bold 22px Inter, system-ui, sans-serif';
        x.textAlign = 'center'; x.fillStyle = h;
        x.fillText(text, 128, 40); x.fillText(text, 128, 40);
        const tex = new THREE.CanvasTexture(c);
        tex.minFilter = THREE.LinearFilter;
        const sp = new THREE.Sprite(new THREE.SpriteMaterial({
            map: tex, transparent: true, opacity: .75,
            depthWrite: false, blending: THREE.AdditiveBlending,
        }));
        sp.scale.set(18, 4.5, 1);
        return sp;
    }

    // ── Animation ────────────────────────────────────────────
    function _animate() {
        animationId = requestAnimationFrame(_animate);
        const t = clock.getElapsedTime();
        const dt = clock.getDelta();

        // Agents vibrate + pulse
        nodeObjects.forEach(mesh => {
            const u = mesh.userData, bp = u.basePos;
            if (!bp) return;

            // Vibrate around base
            const vx = Math.sin(t * u.vFreq + u.vPhase) * u.vAmp;
            const vy = Math.cos(t * u.vFreq * .85 + u.vPhase + 1.3) * u.vAmp * .5;
            const vz = Math.sin(t * u.vFreq * .7 + u.vPhase + 2.6) * u.vAmp * .6;
            mesh.position.set(bp.x + vx, bp.y + vy, bp.z + vz);

            // Pulse — agents breathe visibly, always alive
            const pulseBase = 1 + Math.sin(t * u.pFreq + u.vPhase) * .10;
            const workPulse = Math.sin(t * 3.5 + u.vPhase * 2) * .04; // fast subtle work pulse
            mesh.scale.setScalar(pulseBase + workPulse);

            // Emissive — glow brighter showing constant activity
            const baseGlow = u.baseEmissive + Math.sin(t * 1.1 + u.vPhase) * .12;
            const activityGlow = Math.sin(t * 4 + u.vPhase) * .06; // rapid flicker = working
            mesh.material.emissiveIntensity = baseGlow + activityGlow;

            // Update label position if core
            const label = labelSprites.get(u.id);
            if (label) {
                label.position.set(mesh.position.x, mesh.position.y + u.baseSize + 5, mesh.position.z);
            }
        });

        // Dendrite pulse + fire glow decay
        edgeObjects.forEach(line => {
            const u = line.userData;

            // Active signal is lighting this edge — skip normal pulse
            if (u.fireProgress !== undefined && u.fireProgress > 0) return;

            // Fading after signal passed
            if (u.fireFade !== undefined && u.fireFade > 0) {
                u.fireFade -= dt * 1.8; // fade over ~0.55s
                if (u.fireFade <= 0) {
                    u.fireFade = undefined;
                    u.fireProgress = undefined;
                    u.fireColor = undefined;
                    line.material.color.setHex(u.color || 0x334466);
                } else {
                    const peakOp = Math.min(u.baseOp * 12, 0.65);
                    line.material.opacity = u.baseOp + (peakOp - u.baseOp) * u.fireFade;
                    return;
                }
            }

            // Normal gentle pulse
            const p = Math.sin(t * u.pFreq + u.phase) * .5 + .5;
            line.material.opacity = u.baseOp * (.4 + p * .7);
        });

        // Metatron wireframe pulse
        metatronLines.forEach(line => {
            const u = line.userData;
            line.material.opacity = u.base + Math.sin(t * .6 + u.phase) * u.base * .5;
        });

        // Sacred geometry rotation
        if (sacredGroup) {
            sacredGroup.rotation.y += .0006;
            sacredGroup.rotation.x = Math.sin(t * .08) * .02;
            sacredGroup.rotation.z = Math.cos(t * .05) * .008;
        }

        // Nebula
        if (nebulaParticles) {
            nebulaParticles.rotation.y += .00008;
        }

        // Signals
        _updateSignals();
        signalTimer += dt;
        if (signalTimer > 0.4) { signalTimer = 0; _autoFire(); }

        // Pulses
        _processPulses(t);

        labelSprites.forEach(sp => sp.lookAt(camera.position));

        controls.update();
        renderer.render(scene, camera);
    }

    // ── Pulse effects ────────────────────────────────────────
    function pulseAgent(id) {
        const m = nodeObjects.get(id);
        if (m) pulseQueue.push({ mesh: m, t0: clock.getElapsedTime(), dur: 1.5 });
    }
    function pulseEdge(s, t) { _fireSignal(s, t, 0xFFD700); }
    function _processPulses(t) {
        pulseQueue = pulseQueue.filter(p => {
            const e = t - p.t0;
            if (e > p.dur) { p.mesh.material.emissiveIntensity = p.mesh.userData.baseEmissive; return false; }
            const f = Math.sin((e / p.dur) * Math.PI);
            p.mesh.material.emissiveIntensity = p.mesh.userData.baseEmissive + f * .7;
            p.mesh.scale.setScalar(1 + f * .3);
            return true;
        });
    }

    // ── Interaction ──────────────────────────────────────────
    const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();

    function _onMouseMove(ev) {
        const r = renderer.domElement.getBoundingClientRect();
        mouse.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
        mouse.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
        ray.setFromCamera(mouse, camera);
        const hits = ray.intersectObjects(Array.from(nodeObjects.values()));

        if (hits.length > 0) {
            const hit = hits[0].object;
            if (hoveredNode !== hit) {
                if (hoveredNode) hoveredNode.material.emissiveIntensity = hoveredNode.userData.baseEmissive;
                hoveredNode = hit;
                hoveredNode.material.emissiveIntensity = 1.0;
                renderer.domElement.style.cursor = 'pointer';
                const u = hit.userData, cc = _css(u.agentColor || 0xffffff);
                tooltip.innerHTML =
                    `<div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">` +
                    `<div style="width:10px;height:10px;border-radius:50%;background:${cc};box-shadow:0 0 6px ${cc}"></div>` +
                    `<strong>${u.name || u.id}</strong></div>` +
                    `<span style="opacity:.5;font-size:11px">${u.role || ''}</span>`;
                tooltip.style.display = 'block';
            }
            tooltip.style.left = (ev.clientX - r.left + 15) + 'px';
            tooltip.style.top = (ev.clientY - r.top - 10) + 'px';
        } else {
            if (hoveredNode) {
                hoveredNode.material.emissiveIntensity = hoveredNode.userData.baseEmissive;
                hoveredNode = null;
            }
            renderer.domElement.style.cursor = 'grab';
            tooltip.style.display = 'none';
        }
    }

    function _onClick() {
        if (!hoveredNode) { if (selectedNode) _deselect(); return; }
        _select(hoveredNode);
    }

    function _select(mesh) {
        if (selectedNode === mesh) return;
        if (selectedNode) _deselect();
        selectedNode = mesh;
        const u = mesh.userData, cc = _css(u.agentColor || 0xffffff);
        const div = (u.division||'core').split('_').map(w=>w[0].toUpperCase()+w.slice(1)).join(' ');
        const act = ((u.activity_level||0)*100).toFixed(0);
        const verb = u.activityVerb || ACTIVITY_VERBS[0];

        // Dim unconnected, brighten connected
        const connectedIds = new Set();
        edges.forEach(e => {
            if (e.source === u.id) connectedIds.add(e.target);
            if (e.target === u.id) connectedIds.add(e.source);
        });
        nodeObjects.forEach((m, id) => {
            if (id === u.id) return;
            m.material.opacity = connectedIds.has(id) ? .9 : .12;
        });
        edgeObjects.forEach(l => {
            const e = l.userData;
            if (e.source===u.id||e.target===u.id) {
                l.material.opacity = .4;
                l.material.color.setHex(u.agentColor||0xFFD700);
            } else {
                l.material.opacity = .003;
            }
        });

        const caps = (u.capabilities||[]).slice(0,6).map(c =>
            `<span class="neural-banner-tag">${_escH(typeof c==='object'?c.name:c)}</span>`).join('');

        // Render banner immediately with loading state for connections
        infoPanel.innerHTML = `
            <div class="neural-banner-content">
                <div class="neural-banner-left">
                    <div class="neural-banner-avatar" style="background:${cc};box-shadow:0 0 20px ${cc}">
                        ${_escH((u.name||u.id)[0].toUpperCase())}
                    </div>
                    <div class="neural-banner-identity">
                        <div class="neural-banner-name" style="color:${cc}">${_escH(u.name||u.id)}</div>
                        <div class="neural-banner-role">${_escH(u.role||'Agent')}</div>
                        <div class="neural-banner-activity"><span class="neural-banner-pulse"></span>${_escH(verb)}</div>
                    </div>
                </div>
                <div class="neural-banner-stats">
                    <div class="neural-banner-stat"><span class="neural-banner-stat-value">${_escH(div)}</span><span class="neural-banner-stat-label">Division</span></div>
                    <div class="neural-banner-stat"><span class="neural-banner-stat-value">${u.connections||0}</span><span class="neural-banner-stat-label">Connections</span></div>
                    <div class="neural-banner-stat"><span class="neural-banner-stat-value">${act}%</span><span class="neural-banner-stat-label">Activity</span></div>
                    <div class="neural-banner-stat"><span class="neural-banner-stat-value">${u.tasks_completed||0}</span><span class="neural-banner-stat-label">Tasks</span></div>
                </div>
                <div class="neural-banner-right">
                    ${caps?`<div class="neural-banner-caps">${caps}</div>`:''}
                    <button class="neural-banner-close" onclick="NeuralGalaxy.deselect()">Close</button>
                </div>
            </div>
            <div class="neural-comms-panel" id="neural-comms-panel">
                <div class="neural-comms-loading"><span class="neural-banner-pulse"></span> Loading connections...</div>
            </div>`;
        infoPanel.style.display = 'flex';

        // Fetch real communication data
        _fetchAgentConnections(u.id, cc);
    }

    function _escH(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    async function _fetchAgentConnections(agentId, agentColor) {
        const panel = document.getElementById('neural-comms-panel');
        if (!panel) return;

        try {
            const h = {}; if (window._apiKey) h['X-API-Key'] = window._apiKey;
            const resp = await fetch(`/api/network/agent/${encodeURIComponent(agentId)}/connections?limit=20`, { headers: h });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();

            // If user deselected while loading, bail
            if (!selectedNode || selectedNode.userData.id !== agentId) return;

            const conns = data.connections || [];
            if (conns.length === 0) {
                panel.innerHTML = '<div class="neural-comms-empty">No active communication channels detected</div>';
                return;
            }

            // Separate connections with communication vs structural-only
            const active = conns.filter(c => c.insights.length > 0 || c.collabs.length > 0);
            const structural = conns.filter(c => c.insights.length === 0 && c.collabs.length === 0);

            let html = '<div class="neural-comms-grid">';

            // Active communication channels first
            active.forEach(conn => {
                html += _renderConnectionCard(conn, agentId, agentColor, true);
            });

            // Structural connections (dimmer)
            structural.slice(0, 8).forEach(conn => {
                html += _renderConnectionCard(conn, agentId, agentColor, false);
            });

            html += '</div>';

            if (structural.length > 8) {
                html += `<div class="neural-comms-more">+ ${structural.length - 8} more structural connections</div>`;
            }

            panel.innerHTML = html;

            // Wire up expand toggles
            panel.querySelectorAll('.neural-conn-card[data-expandable]').forEach(card => {
                card.addEventListener('click', () => {
                    card.classList.toggle('expanded');
                    // Fire a signal to the clicked peer
                    const peerId = card.dataset.peerId;
                    if (peerId) {
                        const peerColor = agentColorMap.get(peerId) || 0xFFD700;
                        _fireSignal(agentId, peerId, peerColor);
                    }
                });
            });

        } catch (err) {
            console.error('Failed to fetch agent connections:', err);
            if (panel) panel.innerHTML = '<div class="neural-comms-empty">Could not load connections</div>';
        }
    }

    function _renderConnectionCard(conn, agentId, agentColor, isActive) {
        const peerColor = agentColorMap.get(conn.id);
        const peerCss = peerColor ? _css(peerColor) : '#888';
        const edgeLabel = (conn.edge_types || []).map(t =>
            t === 'core' ? 'Core Link' : t === 'division' ? 'Division' : t === 'insight' ? 'Knowledge' : t
        ).join(', ');

        const insights = conn.insights || [];
        const collabs = conn.collabs || [];
        const hasDetail = insights.length > 0 || collabs.length > 0;

        let commSummary = '';
        if (insights.length > 0 || collabs.length > 0) {
            const incoming = insights.filter(i => i.direction === 'incoming').length;
            const outgoing = insights.filter(i => i.direction === 'outgoing').length;
            const parts = [];
            if (outgoing > 0) parts.push(`${outgoing} sent`);
            if (incoming > 0) parts.push(`${incoming} received`);
            if (collabs.length > 0) parts.push(`${collabs.length} collab${collabs.length > 1 ? 's' : ''}`);
            commSummary = parts.join(' · ');
        }

        // Detail rows for expanded view
        let detailHtml = '';
        if (hasDetail) {
            detailHtml = '<div class="neural-conn-detail">';
            insights.slice(0, 3).forEach(ins => {
                const arrow = ins.direction === 'outgoing' ? '→' : '←';
                const arrowClass = ins.direction === 'outgoing' ? 'outgoing' : 'incoming';
                detailHtml += `
                    <div class="neural-conn-insight">
                        <span class="neural-conn-arrow ${arrowClass}">${arrow}</span>
                        <span class="neural-conn-insight-type">${_escH(ins.type)}</span>
                        <span class="neural-conn-insight-text">${_escH(ins.content)}</span>
                    </div>`;
            });
            collabs.slice(0, 2).forEach(col => {
                detailHtml += `
                    <div class="neural-conn-collab">
                        <span class="neural-conn-collab-icon">⚡</span>
                        <span class="neural-conn-collab-pattern">${_escH(col.pattern)}</span>
                        <span class="neural-conn-collab-goal">${_escH(col.goal)}</span>
                        <span class="neural-conn-collab-status status-${col.status}">${_escH(col.status)}</span>
                    </div>`;
            });
            detailHtml += '</div>';
        }

        return `
            <div class="neural-conn-card ${isActive ? 'active' : 'structural'} ${hasDetail ? '' : 'no-detail'}"
                 ${hasDetail ? 'data-expandable' : ''} data-peer-id="${_escH(conn.id)}">
                <div class="neural-conn-header">
                    <div class="neural-conn-dot" style="background:${peerCss};box-shadow:0 0 8px ${peerCss}"></div>
                    <div class="neural-conn-info">
                        <div class="neural-conn-name" style="color:${peerCss}">${_escH(conn.name)}</div>
                        <div class="neural-conn-role">${_escH(conn.role || conn.division)}</div>
                    </div>
                    <div class="neural-conn-meta">
                        <span class="neural-conn-edge-type">${_escH(edgeLabel)}</span>
                        ${commSummary ? `<span class="neural-conn-comm-summary">${commSummary}</span>` : ''}
                    </div>
                    ${hasDetail ? '<div class="neural-conn-expand-icon">▸</div>' : ''}
                </div>
                ${detailHtml}
            </div>`;
    }

    function _deselect() {
        selectedNode = null;
        edgeObjects.forEach(l => {
            l.material.opacity = l.userData.baseOp;
            l.material.color.setHex(l.userData.color || 0x334466);
        });
        nodeObjects.forEach(m => {
            m.material.opacity = m.userData.division==='core' ? .95 : .85;
        });
        if (infoPanel) infoPanel.style.display = 'none';
    }

    // ── Polling ──────────────────────────────────────────────
    async function _pollActivity() {
        try {
            const h = {}; if (window._apiKey) h['X-API-Key'] = window._apiKey;
            const r = await fetch('/api/network/activity', { headers: h });
            if (r.ok) {
                const d = await r.json();
                (d.recent_agents||[]).forEach(id => pulseAgent(id));
                (d.recent_edges||[]).forEach(e => pulseEdge(e.source, e.target));
            }
        } catch(_){}
        if (isInitialized) setTimeout(_pollActivity, 10000);
    }

    // ── Fallback ─────────────────────────────────────────────
    function _showFallback() {
        const divs = ['core','strategy_council','research','engineering','data_memory',
            'learning','economic','content','automation','infrastructure','governance'];
        const sn = [], se = [];
        let id = 0;
        divs.forEach(d => {
            const c = d==='core'?12:15;
            for (let i=0;i<c;i++) {
                sn.push({id:`a_${id}`,division:d,
                    name:`${d.split('_').map(w=>w[0].toUpperCase()+w.slice(1)).join(' ')} #${i+1}`,
                    role:d,activity_level:Math.random(),connections:Math.floor(Math.random()*8),
                    capabilities:[],tasks_completed:Math.floor(Math.random()*50)});
                id++;
            }
        });
        sn.filter(n=>n.division==='core').forEach(c=>{
            sn.filter(n=>n.division!=='core').slice(0,4).forEach(o=>{
                se.push({source:c.id,target:o.id,type:'core'});
            });
        });
        nodes=sn; edges=se;
        divisions=divs.map(d=>({id:d,name:d,count:d==='core'?12:15}));
        _assignColors(); _buildScene();
    }

    // ── Helpers ──────────────────────────────────────────────
    function _onResize() {
        if (!container||!camera||!renderer) return;
        const W=container.clientWidth, H=container.clientHeight;
        camera.aspect=W/H; camera.updateProjectionMatrix(); renderer.setSize(W,H);
    }
    function _updateStats(s) {
        const el = document.getElementById('neural-stats');
        if (el) el.innerHTML=`<span>${s.total_agents||0} agents</span><span>${s.total_connections||0} connections</span><span>${s.divisions||0} divisions</span>`;
    }
    function _updateLegend() {
        const el = document.getElementById('neural-legend');
        if (!el) return;
        const nm = {core:'Core',strategy_council:'Strategy',research:'Research',
            engineering:'Engineering',data_memory:'Data',learning:'Learning',
            economic:'Economic',content:'Content',automation:'Automation',
            infrastructure:'Infra',governance:'Governance'};
        el.innerHTML = Object.entries(nm).map(([id,name]) => {
            const sa = nodes.find(n=>n.division===id);
            const c = sa ? _css(agentColorMap.get(sa.id)||0x888) : '#888';
            return `<span class="neural-legend-item"><span class="neural-legend-dot" style="background:${c}"></span>${name}</span>`;
        }).join('');
    }

    /**
     * Fire a visible neural signal between two agent nodes.
     * Called externally by WebSocket handlers to visualize real communication.
     * @param {string} srcId - source agent id
     * @param {string} tgtId - target agent id
     * @param {number} [color] - optional hex color override
     */
    function fireSignal(srcId, tgtId, color) {
        if (!isInitialized) return;
        const c = color || (agentColorMap.get(srcId)) || 0xFFD700;
        _fireSignal(srcId, tgtId, c);
    }

    return { init, destroy, pulseAgent, pulseEdge, fireSignal, _boostActivity, deselect: _deselect, refresh: _fetchAndBuild };
})();

// Global cleanup function for use when switching away from the neural panel
function cleanupNeuralGalaxy() {
    if (NeuralGalaxy && typeof NeuralGalaxy.destroy === 'function') {
        NeuralGalaxy.destroy();
    }
}
