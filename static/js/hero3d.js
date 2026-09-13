/* Hero scene: a calm wireframe network of connected nodes with pulses travelling along edges.
   Loaded lazily from home.html only when WebGL is available, motion is allowed and the device is not low-end. */
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js";

const BLUE = new THREE.Color("#1f4fd8");
const BLUE_LIGHT = new THREE.Color("#7fa2ff");

function buildGraph(count, rng) {
  // Nodes arranged in loose tiers, like services talking to each other inside an architecture.
  const nodes = [];
  const tiers = 5;
  for (let i = 0; i < count; i++) {
    const tier = i % tiers;
    const angle = rng() * Math.PI * 2;
    const radius = 1.4 + rng() * 2.6;
    nodes.push(new THREE.Vector3(
      Math.cos(angle) * radius,
      (tier - (tiers - 1) / 2) * 1.05 + (rng() - 0.5) * 0.6,
      Math.sin(angle) * radius,
    ));
  }
  const edges = [];
  const seen = new Set();
  nodes.forEach((a, i) => {
    const nearest = nodes
      .map((b, j) => ({ j, d: a.distanceToSquared(b) }))
      .filter((o) => o.j !== i)
      .sort((x, y) => x.d - y.d)
      .slice(0, 4);
    nearest.forEach(({ j }) => {
      const key = i < j ? `${i}-${j}` : `${j}-${i}`;
      if (!seen.has(key)) { seen.add(key); edges.push([i, j]); }
    });
  });
  return { nodes, edges };
}

function seeded(seed) {
  let s = seed;
  return () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646;
}

export function mountHero(container) {
  const small = window.innerWidth < 700;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
  camera.position.set(0, 0.6, 16);

  const group = new THREE.Group();
  group.rotation.x = 0.28;
  scene.add(group);

  const { nodes, edges } = buildGraph(small ? 46 : 72, seeded(20260913));

  // Edges
  const edgePositions = new Float32Array(edges.length * 6);
  edges.forEach(([a, b], k) => {
    nodes[a].toArray(edgePositions, k * 6);
    nodes[b].toArray(edgePositions, k * 6 + 3);
  });
  const edgeGeo = new THREE.BufferGeometry();
  edgeGeo.setAttribute("position", new THREE.BufferAttribute(edgePositions, 3));
  const edgeMat = new THREE.LineBasicMaterial({ color: BLUE, transparent: true, opacity: 0 });
  group.add(new THREE.LineSegments(edgeGeo, edgeMat));

  // Nodes as small rings (sprite drawn on a canvas so they stay crisp)
  const sprite = document.createElement("canvas");
  sprite.width = sprite.height = 64;
  const ctx = sprite.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.beginPath(); ctx.arc(32, 32, 22, 0, Math.PI * 2); ctx.fill();
  ctx.lineWidth = 7; ctx.strokeStyle = "#1f4fd8";
  ctx.beginPath(); ctx.arc(32, 32, 22, 0, Math.PI * 2); ctx.stroke();
  const nodeTex = new THREE.CanvasTexture(sprite);
  const nodeGeo = new THREE.BufferGeometry().setFromPoints(nodes);
  const nodeMat = new THREE.PointsMaterial({ size: 0.26, map: nodeTex, transparent: true, depthWrite: false, opacity: 0, sizeAttenuation: true });
  group.add(new THREE.Points(nodeGeo, nodeMat));

  // Pulses travelling along random edges
  const pulseCount = small ? 10 : 18;
  const pulsePositions = new Float32Array(pulseCount * 3);
  const pulses = Array.from({ length: pulseCount }, () => ({ edge: Math.floor(Math.random() * edges.length), t: Math.random(), speed: 0.18 + Math.random() * 0.32 }));
  const pulseGeo = new THREE.BufferGeometry();
  pulseGeo.setAttribute("position", new THREE.BufferAttribute(pulsePositions, 3));
  const glow = document.createElement("canvas");
  glow.width = glow.height = 64;
  const g = glow.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(31,79,216,1)");
  grad.addColorStop(0.35, "rgba(127,162,255,0.8)");
  grad.addColorStop(1, "rgba(127,162,255,0)");
  g.fillStyle = grad; g.fillRect(0, 0, 64, 64);
  const pulseMat = new THREE.PointsMaterial({ size: 0.42, map: new THREE.CanvasTexture(glow), transparent: true, depthWrite: false, color: BLUE_LIGHT, opacity: 0 });
  group.add(new THREE.Points(pulseGeo, pulseMat));

  // Sizing
  function resize() {
    const { width, height } = container.getBoundingClientRect();
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  resize();
  const ro = new ResizeObserver(resize);
  ro.observe(container);

  // Pointer parallax (small, eased)
  const target = { x: 0, y: 0 };
  const onPointer = (e) => {
    const r = container.getBoundingClientRect();
    target.x = ((e.clientX - r.left) / r.width - 0.5) * 0.35;
    target.y = ((e.clientY - r.top) / r.height - 0.5) * 0.2;
  };
  window.addEventListener("pointermove", onPointer, { passive: true });

  // Settle in
  const intro = { p: 0 };
  if (window.gsap) {
    window.gsap.to(intro, { p: 1, duration: 2.2, ease: "power3.out" });
  } else {
    intro.p = 1;
  }

  const clock = new THREE.Clock();
  let running = true;
  let rafId = 0;

  function frame() {
    if (!running) return;
    rafId = requestAnimationFrame(frame);
    const dt = Math.min(clock.getDelta(), 0.05);
    const time = clock.elapsedTime;

    edgeMat.opacity = 0.32 * intro.p;
    nodeMat.opacity = intro.p;
    pulseMat.opacity = intro.p;
    camera.position.z = 16 - 3.4 * intro.p;

    group.rotation.y += dt * 0.06;
    group.rotation.x += (0.28 + target.y - group.rotation.x) * 0.04;
    group.position.x += (target.x - group.position.x) * 0.04;
    group.position.y = Math.sin(time * 0.4) * 0.08;

    pulses.forEach((pulse, k) => {
      pulse.t += dt * pulse.speed;
      if (pulse.t >= 1) {
        pulse.t = 0;
        const [, end] = edges[pulse.edge];
        const next = edges.filter(([a]) => a === end);
        pulse.edge = next.length ? edges.indexOf(next[Math.floor(Math.random() * next.length)]) : Math.floor(Math.random() * edges.length);
      }
      const [a, b] = edges[pulse.edge];
      const p = nodes[a].clone().lerp(nodes[b], pulse.t);
      p.toArray(pulsePositions, k * 3);
    });
    pulseGeo.attributes.position.needsUpdate = true;

    renderer.render(scene, camera);
  }

  // Only render while visible
  const io = new IntersectionObserver((entries) => {
    const visible = entries[0].isIntersecting && !document.hidden;
    if (visible && !running) { running = true; clock.getDelta(); frame(); }
    if (!visible) { running = false; cancelAnimationFrame(rafId); }
  });
  io.observe(container);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) { running = false; cancelAnimationFrame(rafId); }
    else if (!running) { running = true; clock.getDelta(); frame(); }
  });

  frame();
  container.parentElement.classList.add("has-webgl");

  return () => {
    running = false;
    cancelAnimationFrame(rafId);
    io.disconnect();
    ro.disconnect();
    window.removeEventListener("pointermove", onPointer);
    renderer.dispose();
    container.innerHTML = "";
  };
}
