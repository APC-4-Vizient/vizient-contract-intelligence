import {
  AdditiveBlending,
  Color,
  DirectionalLight,
  DoubleSide,
  Group,
  HemisphereLight,
  InstancedMesh,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  NoToneMapping,
  PerspectiveCamera,
  PlaneGeometry,
  Raycaster,
  Scene,
  SphereGeometry,
  Sprite,
  SpriteMaterial,
  Vector2,
  Vector3,
  WebGLRenderer,
} from 'three';
import type { BufferGeometry, Material, Object3D, Texture } from 'three';
import { EDGES, NODES, NODE_BY_ID, STEPS, ZONES, ZONE_BY_ID } from '../architecture';
import type { ArchEdge, ArchNode, EdgeId, NodeId, ZoneId } from '../architecture';
import { CameraRig } from './cameraRig';
import { clamp, damp, easeInOutCubic, easeOutCubic, framePoints, locateAlong, samplePolyline, smoothstep } from './math';
import type { CameraPose } from './math';
import { createGlowTexture, createPaperTexture, createScreenTexture } from './textures';
import { buildVisual } from './visuals';
import type { NodeVisual, VisualAssets } from './visuals';
import { buildEdge, buildFloor, buildPad, buildZones } from './world';
import type { EdgeVisual, PadVisual } from './world';

export interface EngineOptions {
  /** Holds the canvas, which the engine adds, and is measured for size. It must be positioned. */
  container: HTMLElement;
  /** Holds the label elements the engine moves into place. */
  labels: HTMLElement;
  motion: boolean;
  onHover(id: NodeId | null): void;
  onSelect(id: NodeId | null): void;
}

export interface Engine {
  setStep(index: number | null): void;
  setSelected(id: NodeId | null): void;
  setHovered(id: NodeId | null): void;
  setMotion(on: boolean): void;
  /** Hand the camera back to the story: clears the viewer's own rotation and zoom. */
  resetView(): void;
  zoomBy(factor: number): void;
  dispose(): void;
}

const FOV = 36;
const MAX_PIXEL_RATIO = 1.75;
const PAD_HEIGHT = 0.12;
/** A step's animation repeats at this interval while the story rests on it. */
const LOOP_SECONDS = 6.5;
const OVERVIEW_POLAR = 0.9;
const STEP_POLAR = 0.95;
const STEP_SWING = 0.1;
const DRAG_AZIMUTH = 0.0052;
const DRAG_POLAR = 0.0042;
const CLICK_SLOP = 5;
const FINDING_COUNT = 20;
const DETAIL_COUNT = 9;
const EDGE_LABEL_LIFT = new Vector3(0, 0.55, 0);
/** The contract status rides this many pixels above the Dataverse label, whatever the zoom. */
const STATUS_GAP = 8;
/** A label closer than this to the edge of the stage fades out instead of being cut in half. */
const CLIP_MARGIN = 6;

const OVERVIEW_POINTS: readonly (readonly [number, number, number])[] = ZONES.flatMap((zone) =>
  zone.slabs.flatMap((slab) => [
    [slab.x - slab.width / 2, 0, slab.z - slab.depth / 2] as const,
    [slab.x + slab.width / 2, 0, slab.z + slab.depth / 2] as const,
  ]),
);

interface NodeRuntime {
  node: ArchNode;
  visual: NodeVisual;
  pad: PadVisual;
  energy: number;
  emphasis: number;
  active: number;
}

interface EdgeRuntime {
  edge: ArchEdge;
  visual: EdgeVisual;
  energy: number;
}

interface LabelAnchor {
  element: HTMLElement;
  world: Vector3;
  center: boolean;
  /** Pixels the label is raised above its projected point, so it clears what sits there. */
  lift: number;
  width: number;
  height: number;
  clipped: boolean;
  last: string;
}

interface TravelData {
  paths: Vector3[][];
  lengths: number[];
}

function nodeOf(id: NodeId): ArchNode {
  const node = NODE_BY_ID.get(id);
  if (!node) throw new Error(`Unknown node ${id}`);
  return node;
}

function disposeTree(root: Object3D): void {
  root.traverse((object) => {
    const target = object as Object3D & { geometry?: BufferGeometry; material?: Material | Material[] };
    target.geometry?.dispose();
    const materials = Array.isArray(target.material) ? target.material : target.material ? [target.material] : [];
    for (const material of materials) material.dispose();
  });
}

export function createEngine(options: EngineOptions): Engine {
  const { container, labels } = options;

  // Each engine makes its own canvas: a canvas whose context was force-lost cannot be reused for a new renderer.
  const canvas = document.createElement('canvas');
  canvas.className = 'arch__canvas';
  canvas.setAttribute('aria-hidden', 'true');
  container.prepend(canvas);

  let renderer: WebGLRenderer;
  try {
    renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  } catch (error) {
    canvas.remove();
    throw error;
  }
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = NoToneMapping;

  const scene = new Scene();
  const camera = new PerspectiveCamera(FOV, 2, 0.5, 260);

  const hemisphere = new HemisphereLight('#ffeedd', '#3a1426', 1.5);
  const key = new DirectionalLight('#fff1e2', 2.5);
  key.position.set(-8, 14, 10);
  const rimLight = new DirectionalLight('#9bc4ff', 1);
  rimLight.position.set(10, 6, -10);
  scene.add(hemisphere, key, rimLight);

  const glow = createGlowTexture();
  const assets: VisualAssets = { glow, paper: createPaperTexture(), screen: createScreenTexture() };
  const textures: Texture[] = [assets.glow, assets.paper, assets.screen];

  const floor = buildFloor();
  scene.add(floor.mesh, buildZones());

  const hitOwner = new Map<Object3D, NodeId>();
  const hitMeshes: Mesh[] = [];
  const nodes: NodeRuntime[] = NODES.map((node) => {
    const pad = buildPad(node);
    const visual = buildVisual(node.kind, assets);
    visual.group.position.set(node.position[0], PAD_HEIGHT, node.position[2]);
    const hit = new Mesh(new SphereGeometry(visual.hitRadius, 14, 10), new MeshBasicMaterial({ visible: false }));
    hit.position.set(node.position[0], PAD_HEIGHT + visual.hitY, node.position[2]);
    hitOwner.set(hit, node.id);
    hitMeshes.push(hit);
    scene.add(pad.group, visual.group, hit);
    return { node, pad, visual, energy: 0.8, emphasis: 0, active: 0 };
  });
  const analyzerVisual = nodes.find((runtime) => runtime.node.id === 'analyzer')?.visual;

  const edges: EdgeRuntime[] = EDGES.map((edge) => {
    const visual = buildEdge(edge, glow);
    scene.add(visual.group);
    return { edge, visual, energy: 0.5 };
  });
  const edgeRuntime = new Map<EdgeId, EdgeRuntime>(edges.map((runtime) => [runtime.edge.id, runtime]));

  // The contract tile that travels the pipeline, and the 20 chips that stream back as findings.
  const tile = new Group();
  const tileMaterial = new MeshBasicMaterial({ map: assets.paper, transparent: true, side: DoubleSide, toneMapped: false, depthWrite: false });
  const tileGlowMaterial = new SpriteMaterial({ map: glow, color: '#ff9a4d', transparent: true, opacity: 0.7, depthWrite: false, blending: AdditiveBlending });
  const tileGlow = new Sprite(tileGlowMaterial);
  tileGlow.scale.setScalar(2.8);
  tile.add(tileGlow, new Mesh(new PlaneGeometry(1, 1.3), tileMaterial));
  tile.visible = false;
  tile.renderOrder = 10;
  scene.add(tile);

  const chips = new InstancedMesh(
    new PlaneGeometry(0.56, 0.36),
    new MeshBasicMaterial({ transparent: true, opacity: 0.95, toneMapped: false, depthWrite: false, side: DoubleSide }),
    FINDING_COUNT,
  );
  const detailColor = new Color('#7fb6e0');
  const rightColor = new Color('#ff9a4d');
  for (let i = 0; i < FINDING_COUNT; i += 1) chips.setColorAt(i, i < DETAIL_COUNT ? detailColor : rightColor);
  chips.frustumCulled = false;
  chips.visible = false;
  chips.renderOrder = 9;
  scene.add(chips);
  scene.updateMatrixWorld(true);

  const rig = new CameraRig(camera, framePoints(OVERVIEW_POINTS, overviewOptions(2)));

  let motion = options.motion;
  let stepIndex: number | null = null;
  let selected: NodeId | null = null;
  let hovered: NodeId | null = null;
  let width = 0;
  let height = 0;
  let animTime = 0;
  let stepStart = 0;
  let lastTs = 0;
  let raf = 0;
  let inView = true;
  let tabVisible = !document.hidden;
  let visible = inView && tabVisible;
  let disposed = false;
  let contextLost = false;
  let labelsDirty = true;
  let anchorsStale = true;
  let anchors: LabelAnchor[] = [];

  function overviewOptions(aspect: number) {
    return { fovDeg: FOV, aspect, polar: OVERVIEW_POLAR, azimuth: 0, padX: 0.6, padZ: 0.5, minWidth: 0, heightY: 5, targetY: 1.6 };
  }

  function focusPose(ids: readonly NodeId[], azimuth: number): CameraPose {
    return framePoints(
      ids.map((id) => nodeOf(id).position),
      { fovDeg: FOV, aspect: camera.aspect, polar: STEP_POLAR, azimuth, padX: 3, padZ: 2.5, minWidth: 13, heightY: 5.4, targetY: 1.6 },
    );
  }

  function basePose(): CameraPose {
    if (stepIndex !== null) return focusPose(STEPS[stepIndex].focus, motion ? (stepIndex % 2 === 0 ? STEP_SWING : -STEP_SWING) : 0);
    if (selected !== null) return focusPose([selected], 0);
    return framePoints(OVERVIEW_POINTS, overviewOptions(camera.aspect));
  }

  const travelCache = new Map<number, TravelData>();
  function travelOf(index: number): TravelData {
    let data = travelCache.get(index);
    if (!data) {
      const paths: Vector3[][] = [];
      const lengths: number[] = [];
      for (const hop of STEPS[index].travel) {
        const runtime = edgeRuntime.get(hop.edge);
        if (!runtime) continue;
        paths.push(hop.reverse ? [...runtime.visual.path].reverse() : runtime.visual.path);
        lengths.push(runtime.visual.length);
      }
      data = { paths, lengths };
      travelCache.set(index, data);
    }
    return data;
  }

  const point = new Vector3();
  const scale = new Vector3();
  const matrix = new Matrix4();

  function showTile(x: number, y: number, z: number, opacity: number, size: number): void {
    if (opacity <= 0.01) return;
    tile.visible = true;
    tile.position.set(x, y, z);
    tile.scale.setScalar(size);
    tile.quaternion.copy(camera.quaternion);
    tileMaterial.opacity = opacity;
    tileGlowMaterial.opacity = 0.7 * opacity;
  }

  function placeEnterTile(node: ArchNode, t: number): void {
    const drop = easeOutCubic((t - 0.2) / 1);
    const sink = smoothstep(2.2, 3, t);
    const y = PAD_HEIGHT + 1.55 + (1 - drop) * 4.05 - sink * 0.7;
    const bob = Math.sin(animTime * 3.2) * 0.05;
    showTile(node.position[0], y + bob, node.position[2], smoothstep(0.2, 0.5, t) * (1 - sink), 1);
  }

  function placeTravelTile(index: number, t: number): void {
    const data = travelOf(index);
    if (data.paths.length === 0) return;
    const { index: hop, local } = locateAlong(data.lengths, easeInOutCubic((t - 0.4) / 3.4));
    samplePolyline(data.paths[hop], local, point);
    const bob = Math.sin(animTime * 3.2) * 0.05;
    const appear = smoothstep(0, 0.3, t);
    const fade = 1 - smoothstep(4.2, 4.8, t);
    showTile(point.x, point.y + bob, point.z, appear * fade, 0.55 + 0.45 * easeOutCubic(t / 0.35));
  }

  function placeChips(t: number): void {
    const results = edgeRuntime.get('results');
    if (!results) return;
    chips.visible = true;
    for (let i = 0; i < FINDING_COUNT; i += 1) {
      let along = 0;
      let size = 0;
      if (motion) {
        const local = (t - (0.35 + i * 0.14)) / 2.2;
        if (local > 0 && local < 1) {
          along = easeInOutCubic(local);
          size = smoothstep(0, 0.12, local) * (1 - smoothstep(0.86, 1, local));
        }
      } else {
        along = (i + 0.5) / FINDING_COUNT;
        size = 1;
      }
      samplePolyline(results.visual.path, along, point);
      scale.setScalar(Math.max(size, 0.0001));
      matrix.compose(point, camera.quaternion, scale);
      chips.setMatrixAt(i, matrix);
    }
    chips.instanceMatrix.needsUpdate = true;
  }

  function updateStory(): void {
    tile.visible = false;
    chips.visible = false;
    let scan: number | null = null;
    const step = stepIndex === null ? null : STEPS[stepIndex];
    if (stepIndex !== null && step) {
      const t = motion ? (animTime - stepStart) % LOOP_SECONDS : step.enter ? 1.5 : 3.8;
      if (step.enter) placeEnterTile(nodeOf(step.enter), t);
      else if (step.travel.length > 0) placeTravelTile(stepIndex, t);
      if (step.effect === 'findings') placeChips(t);
      if (step.effect === 'scan') scan = motion ? (t >= 0.9 && t <= 4.1 ? (t - 0.9) / 3.2 : null) : 0.2;
    }
    analyzerVisual?.setScan?.(scan);
  }

  /** Ease every node and edge toward how lit it should be. Returns true while anything is still easing. */
  function advance(real: number, dt: number): boolean {
    const k = motion ? damp(6, real) : 1;
    const step = stepIndex === null ? null : STEPS[stepIndex];
    let gap = 0;

    for (const runtime of nodes) {
      const id = runtime.node.id;
      const chosen = selected === id || hovered === id;
      const inFocus = step !== null && step.focus.includes(id);
      const targetEnergy = chosen || inFocus ? 1 : step !== null ? 0.32 : selected !== null ? 0.55 : 0.8;
      const targetActive = inFocus ? 1 : 0;
      const targetEmphasis = chosen ? 1 : 0;
      runtime.energy += (targetEnergy - runtime.energy) * k;
      runtime.active += (targetActive - runtime.active) * k;
      runtime.emphasis += (targetEmphasis - runtime.emphasis) * k;
      gap = Math.max(gap, Math.abs(targetEnergy - runtime.energy), Math.abs(targetActive - runtime.active), Math.abs(targetEmphasis - runtime.emphasis));
      runtime.visual.update({ time: animTime, dt, energy: runtime.energy, emphasis: runtime.emphasis, active: runtime.active });
      runtime.pad.update(runtime.energy, runtime.emphasis, animTime);
    }

    for (const runtime of edges) {
      const { from, to, id } = runtime.edge;
      const lit = (step !== null && step.edges.includes(id)) || [selected, hovered].some((chosen) => chosen !== null && (chosen === from || chosen === to));
      const target = lit ? 1 : step !== null ? 0.18 : selected !== null ? 0.3 : 0.5;
      runtime.energy += (target - runtime.energy) * k;
      gap = Math.max(gap, Math.abs(target - runtime.energy));
      runtime.visual.update(dt, runtime.energy);
    }
    return gap > 0.003;
  }

  function anchorWorld(kind: string | undefined, id: string | undefined): Vector3 | null {
    if (kind === 'node') {
      const node = id ? NODE_BY_ID.get(id as NodeId) : undefined;
      return node ? new Vector3(node.position[0], node.labelY, node.position[2]) : null;
    }
    if (kind === 'edge') {
      const runtime = id ? edgeRuntime.get(id as EdgeId) : undefined;
      if (!runtime) return null;
      const world = runtime.visual.midpoint.clone().add(EDGE_LABEL_LIFT);
      const offset = runtime.edge.captionOffset;
      if (offset) world.add(new Vector3(offset[0], offset[1], offset[2]));
      return world;
    }
    if (kind === 'zone') {
      const zone = id ? ZONE_BY_ID.get(id as ZoneId) : undefined;
      return zone ? new Vector3(zone.labelAt[0], 0.05, zone.labelAt[1]) : null;
    }
    if (kind === 'status') {
      const dataverse = nodeOf('dataverse');
      return new Vector3(dataverse.position[0], dataverse.labelY, dataverse.position[2]);
    }
    return null;
  }

  function collectAnchors(): void {
    anchors = [];
    const dataverseLabel = labels.querySelector<HTMLElement>('[data-anchor="node"][data-id="dataverse"]');
    labels.querySelectorAll<HTMLElement>('[data-anchor]').forEach((element) => {
      const kind = element.dataset.anchor;
      const world = anchorWorld(kind, element.dataset.id);
      if (!world) return;
      anchors.push({
        element,
        world,
        center: kind === 'zone',
        lift: kind === 'status' ? (dataverseLabel?.offsetHeight ?? 0) + STATUS_GAP : 0,
        width: element.offsetWidth,
        height: element.offsetHeight,
        clipped: element.hasAttribute('data-clipped'),
        last: '',
      });
    });
    anchorsStale = false;
  }

  const projected = new Vector3();
  function projectLabels(): void {
    if (anchorsStale) collectAnchors();
    for (const anchor of anchors) {
      projected.copy(anchor.world).project(camera);
      const x = (projected.x * 0.5 + 0.5) * width;
      const y = (-projected.y * 0.5 + 0.5) * height - anchor.lift;
      const transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(-50%, ${anchor.center ? '-50%' : '-100%'})`;
      if (transform !== anchor.last) {
        anchor.element.style.transform = transform;
        anchor.last = transform;
      }
      anchor.element.style.zIndex = String(Math.round(100000 / Math.max(camera.position.distanceTo(anchor.world), 1)));

      const top = anchor.center ? y - anchor.height / 2 : y - anchor.height;
      const clipped =
        projected.z > 1 ||
        x - anchor.width / 2 < CLIP_MARGIN ||
        x + anchor.width / 2 > width - CLIP_MARGIN ||
        top < CLIP_MARGIN ||
        top + anchor.height > height - CLIP_MARGIN;
      if (clipped !== anchor.clipped) {
        anchor.clipped = clipped;
        anchor.element.toggleAttribute('data-clipped', clipped);
      }
    }
    labelsDirty = false;
  }

  function render(): void {
    if (contextLost || width === 0) return;
    renderer.render(scene, camera);
  }

  function request(): void {
    if (raf === 0 && !disposed && visible) raf = requestAnimationFrame(frame);
  }

  function frame(timestamp: number): void {
    raf = 0;
    if (disposed) return;
    const real = lastTs === 0 ? 1 / 60 : Math.min(0.1, (timestamp - lastTs) / 1000);
    lastTs = timestamp;
    const dt = motion ? real : 0;
    animTime += dt;

    let busy = advance(real, dt);
    if (floor.update(real)) busy = true;
    const cameraBusy = rig.update(real, motion ? animTime : null);
    updateStory();
    if (cameraBusy || labelsDirty) projectLabels();
    render();

    if (visible && !contextLost && (motion || busy || cameraBusy)) request();
    else lastTs = 0;
  }

  function resize(): void {
    const w = container.clientWidth;
    const h = container.clientHeight;
    if (w < 2 || h < 2) return;
    width = w;
    height = h;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, MAX_PIXEL_RATIO));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    rig.setBase(basePose(), { instant: true, keepUser: true });
    updateStory();
    anchorsStale = true;
    projectLabels();
    render();
    request();
  }

  function updateVisible(): void {
    visible = inView && tabVisible;
    if (visible) {
      labelsDirty = true;
      request();
    }
  }

  const pointer = new Vector2();
  const raycaster = new Raycaster();
  function pick(clientX: number, clientY: number): NodeId | null {
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;
    pointer.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    camera.updateMatrixWorld();
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObjects(hitMeshes, false)[0];
    return hit ? (hitOwner.get(hit.object) ?? null) : null;
  }

  let drag: { pointerId: number; startX: number; startY: number; lastX: number; lastY: number; moved: boolean } | null = null;

  function setHover(id: NodeId | null): void {
    if (id === hovered) return;
    hovered = id;
    canvas.style.cursor = id ? 'pointer' : 'grab';
    options.onHover(id);
    request();
  }

  function onPointerDown(event: PointerEvent): void {
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    drag = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, lastX: event.clientX, lastY: event.clientY, moved: false };
    canvas.setPointerCapture(event.pointerId);
    canvas.style.cursor = 'grabbing';
  }

  function onPointerMove(event: PointerEvent): void {
    if (drag && event.pointerId === drag.pointerId) {
      if (!drag.moved && Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) < CLICK_SLOP) return;
      drag.moved = true;
      rig.drag(-(event.clientX - drag.lastX) * DRAG_AZIMUTH, -(event.clientY - drag.lastY) * DRAG_POLAR);
      drag.lastX = event.clientX;
      drag.lastY = event.clientY;
      labelsDirty = true;
      request();
      return;
    }
    if (event.pointerType === 'mouse') setHover(pick(event.clientX, event.clientY));
  }

  function onPointerUp(event: PointerEvent): void {
    if (!drag || event.pointerId !== drag.pointerId) return;
    const wasClick = !drag.moved && event.type === 'pointerup';
    drag = null;
    canvas.style.cursor = hovered ? 'pointer' : 'grab';
    if (wasClick) options.onSelect(pick(event.clientX, event.clientY));
  }

  function onPointerLeave(): void {
    if (!drag) setHover(null);
  }

  // Only Ctrl+scroll (and a trackpad pinch, which arrives the same way) zooms; plain scrolling still scrolls the page.
  function onWheel(event: WheelEvent): void {
    if (!event.ctrlKey) return;
    event.preventDefault();
    rig.zoomBy(Math.exp(event.deltaY * 0.002));
    labelsDirty = true;
    request();
  }

  function onContextLost(event: Event): void {
    event.preventDefault();
    contextLost = true;
  }

  function onContextRestored(): void {
    contextLost = false;
    labelsDirty = true;
    request();
  }

  const onVisibility = (): void => {
    tabVisible = !document.hidden;
    updateVisible();
  };

  canvas.style.cursor = 'grab';
  canvas.addEventListener('pointerdown', onPointerDown);
  canvas.addEventListener('pointermove', onPointerMove);
  canvas.addEventListener('pointerup', onPointerUp);
  canvas.addEventListener('pointercancel', onPointerUp);
  canvas.addEventListener('pointerleave', onPointerLeave);
  canvas.addEventListener('wheel', onWheel, { passive: false });
  canvas.addEventListener('webglcontextlost', onContextLost);
  canvas.addEventListener('webglcontextrestored', onContextRestored);
  document.addEventListener('visibilitychange', onVisibility);

  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(container);
  const intersectionObserver = new IntersectionObserver((entries) => {
    inView = entries.some((entry) => entry.isIntersecting);
    updateVisible();
  });
  intersectionObserver.observe(container);
  const mutationObserver = new MutationObserver(() => {
    anchorsStale = true;
    labelsDirty = true;
    request();
  });
  mutationObserver.observe(labels, { childList: true, subtree: true, characterData: true });

  resize();
  request();

  return {
    setStep(index) {
      const next = index !== null && index >= 0 && index < STEPS.length ? index : null;
      if (next === stepIndex) return;
      stepIndex = next;
      stepStart = animTime;
      rig.setBase(basePose(), { instant: !motion, keepUser: false });
      if (next !== null && motion) {
        const step = STEPS[next];
        const arriving = nodeOf(step.focus[step.focus.length - 1]);
        floor.ping(arriving.position[0], arriving.position[2], arriving.color);
      }
      labelsDirty = true;
      request();
    },
    setSelected(id) {
      if (id === selected) return;
      selected = id;
      if (stepIndex === null) rig.setBase(basePose(), { instant: !motion, keepUser: false });
      labelsDirty = true;
      request();
    },
    setHovered(id) {
      if (id === hovered) return;
      hovered = id;
      request();
    },
    setMotion(on) {
      if (on === motion) return;
      motion = on;
      stepStart = animTime;
      rig.setBase(basePose(), { instant: true, keepUser: true });
      labelsDirty = true;
      request();
    },
    resetView() {
      rig.resetUser();
      rig.setBase(basePose(), { instant: !motion, keepUser: false });
      labelsDirty = true;
      request();
    },
    zoomBy(factor) {
      rig.zoomBy(clamp(factor, 0.5, 2));
      labelsDirty = true;
      request();
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      cancelAnimationFrame(raf);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      mutationObserver.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerup', onPointerUp);
      canvas.removeEventListener('pointercancel', onPointerUp);
      canvas.removeEventListener('pointerleave', onPointerLeave);
      canvas.removeEventListener('wheel', onWheel);
      canvas.removeEventListener('webglcontextlost', onContextLost);
      canvas.removeEventListener('webglcontextrestored', onContextRestored);
      disposeTree(scene);
      chips.dispose();
      for (const texture of textures) texture.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
    },
  };
}
