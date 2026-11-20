import {
  AdditiveBlending,
  BoxGeometry,
  CapsuleGeometry,
  CircleGeometry,
  Color,
  ConeGeometry,
  CylinderGeometry,
  DoubleSide,
  EdgesGeometry,
  ExtrudeGeometry,
  Group,
  IcosahedronGeometry,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PlaneGeometry,
  Shape,
  SphereGeometry,
  Sprite,
  SpriteMaterial,
  TorusGeometry,
} from 'three';
import type { Texture } from 'three';
import type { NodeKind } from '../architecture';
import { clamp } from './math';

/** What the engine tells a node's visual each frame. */
export interface FrameState {
  /** Animated seconds. Stands still while motion is off. */
  time: number;
  /** Seconds since the last frame. Zero while motion is off. */
  dt: number;
  /** 0 is dimmed, 1 is fully lit. */
  energy: number;
  /** 0 to 1: the node is hovered or selected. */
  emphasis: number;
  /** 0 to 1: the node is doing something in the current step. */
  active: number;
}

export interface NodeVisual {
  group: Group;
  /** Radius and height of the invisible sphere used for picking. */
  hitRadius: number;
  hitY: number;
  update(frame: FrameState): void;
  /** Only the analyzer has a scan beam. `null` hides it. */
  setScan?(progress: number | null): void;
}

export interface VisualAssets {
  glow: Texture;
  paper: Texture;
  screen: Texture;
}

type FadeMaterial = MeshBasicMaterial | SpriteMaterial | LineBasicMaterial;

/** Remembers each material's resting look so a node can be dimmed and brightened as a whole. */
class Lit {
  private readonly solids: { material: MeshStandardMaterial; color: Color; emissive: number }[] = [];
  private readonly flats: { material: MeshBasicMaterial; color: Color }[] = [];
  private readonly glows: { material: FadeMaterial; opacity: number }[] = [];

  solid(material: MeshStandardMaterial): MeshStandardMaterial {
    this.solids.push({ material, color: material.color.clone(), emissive: material.emissiveIntensity });
    return material;
  }

  flat(material: MeshBasicMaterial): MeshBasicMaterial {
    this.flats.push({ material, color: material.color.clone() });
    return material;
  }

  glow<T extends FadeMaterial>(material: T): T {
    material.transparent = true;
    this.glows.push({ material, opacity: material.opacity });
    return material;
  }

  apply(energy: number, boost: number): void {
    const body = 0.5 + 0.5 * energy;
    const light = 0.2 + 0.8 * energy;
    for (const item of this.solids) {
      item.material.color.copy(item.color).multiplyScalar(body);
      item.material.emissiveIntensity = item.emissive * light * (1 + boost);
    }
    for (const item of this.flats) item.material.color.copy(item.color).multiplyScalar(0.42 + 0.58 * energy + boost * 0.12);
    for (const item of this.glows) item.material.opacity = clamp(item.opacity * light * (1 + boost * 0.8), 0, 1);
  }
}

function standard(color: string, emissive: string, emissiveIntensity: number, roughness = 0.45, metalness = 0.15): MeshStandardMaterial {
  return new MeshStandardMaterial({ color, emissive, emissiveIntensity, roughness, metalness });
}

function glowSprite(lit: Lit, texture: Texture, color: string, scale: number, opacity: number): Sprite {
  const sprite = new Sprite(
    lit.glow(new SpriteMaterial({ map: texture, color, opacity, depthWrite: false, blending: AdditiveBlending })),
  );
  sprite.scale.setScalar(scale);
  return sprite;
}

function additive(color: string, opacity: number): MeshBasicMaterial {
  return new MeshBasicMaterial({ color, opacity, transparent: true, depthWrite: false, blending: AdditiveBlending, side: DoubleSide });
}

function buildLibrary(assets: VisualAssets, lit: Lit): NodeVisual {
  const group = new Group();
  const folder = lit.solid(standard('#2f6a98', '#7fb6e0', 0.2, 0.55));
  const body = new Mesh(new BoxGeometry(3.1, 0.7, 2.1), folder);
  body.position.y = 0.35;
  const tab = new Mesh(new BoxGeometry(1.15, 0.14, 0.5), folder);
  tab.position.set(-0.95, 0.77, -0.8);
  const lip = new Mesh(new BoxGeometry(3.12, 0.08, 0.06), lit.solid(standard('#9ccbee', '#9ccbee', 0.6, 0.4)));
  lip.position.set(0, 0.46, 1.06);
  group.add(body, tab, lip);

  const pageMaterial = lit.flat(new MeshBasicMaterial({ map: assets.paper, side: DoubleSide }));
  const pageGeometry = new PlaneGeometry(1.25, 1.62);
  const resting = [
    { x: -0.62, y: 1.42, z: 0.12, yaw: -0.22 },
    { x: 0, y: 1.62, z: -0.05, yaw: 0 },
    { x: 0.62, y: 1.82, z: -0.22, yaw: 0.22 },
  ];
  const pages = resting.map((spot) => {
    const page = new Mesh(pageGeometry, pageMaterial);
    page.position.set(spot.x, spot.y, spot.z);
    page.rotation.set(-1.0, spot.yaw, 0, 'YXZ');
    group.add(page);
    return page;
  });

  let phase = 0;
  return {
    group,
    hitRadius: 2.1,
    hitY: 1.0,
    update(frame) {
      lit.apply(frame.energy, frame.emphasis * 0.5 + frame.active * 0.35);
      phase += frame.dt;
      pages.forEach((page, index) => {
        page.position.y = resting[index].y + Math.sin(phase * 1.3 + index * 1.7) * 0.07 + frame.active * 0.16;
        page.rotation.z = Math.sin(phase * 0.9 + index) * 0.05;
      });
    },
  };
}

function buildFlow(assets: VisualAssets, lit: Lit, double: boolean): NodeVisual {
  const group = new Group();
  // The ring stands in the YZ plane so a contract travelling along x passes through it.
  const pivot = new Group();
  pivot.position.y = 1.2;
  pivot.rotation.y = Math.PI / 2;
  group.add(pivot);

  const orange = lit.solid(standard('#f67318', '#f67318', 0.9, 0.35, 0.25));
  const pale = lit.solid(standard('#ffd2b0', '#ff9a4d', 0.7, 0.4, 0.1));

  const arcWithHead = (radius: number, tube: number, arc: number, material: MeshStandardMaterial): Group => {
    const spin = new Group();
    spin.add(new Mesh(new TorusGeometry(radius, tube, 16, 72, arc), material));
    const head = new Mesh(new ConeGeometry(tube * 1.7, tube * 4, 4), material);
    head.position.set(Math.cos(arc) * radius, Math.sin(arc) * radius, 0);
    head.rotation.z = arc;
    spin.add(head);
    return spin;
  };

  const outer = arcWithHead(1.0, 0.13, Math.PI * 1.5, orange);
  pivot.add(outer);
  const middle = double ? arcWithHead(0.7, 0.09, Math.PI * 1.2, pale) : null;
  if (middle) pivot.add(middle);
  const inner = new Mesh(new TorusGeometry(double ? 0.4 : 0.62, 0.045, 12, 64), pale);
  pivot.add(inner);
  const core = new Mesh(new SphereGeometry(0.17, 20, 16), lit.solid(standard('#fff1e6', '#ff9a4d', 1.3, 0.3, 0)));
  pivot.add(core);

  const glow = glowSprite(lit, assets.glow, '#f67318', 2.9, 0.5);
  glow.position.y = 1.2;
  group.add(glow);

  let outerAngle = 0;
  let middleAngle = 0;
  let phase = 0;
  return {
    group,
    hitRadius: 1.6,
    hitY: 1.2,
    update(frame) {
      lit.apply(frame.energy, frame.emphasis * 0.5 + frame.active * 0.5);
      const speed = 0.9 + frame.active * 2.6;
      phase += frame.dt;
      outerAngle += frame.dt * speed;
      outer.rotation.z = outerAngle;
      if (middle) {
        middleAngle -= frame.dt * speed * 1.35;
        middle.rotation.z = middleAngle;
      }
      inner.rotation.x = phase * 0.6;
      const pulse = 1 + Math.sin(phase * 2.4) * 0.06 + frame.active * 0.35;
      core.scale.setScalar(pulse);
      glow.scale.setScalar(2.9 * (0.95 + frame.active * 0.28 + Math.sin(phase * 2) * 0.04));
    },
  };
}

function buildTables(assets: VisualAssets, lit: Lit): NodeVisual {
  const group = new Group();
  const colors = ['#cfc0c8', '#eee8ec', '#fefcf8'];
  const rimMaterial = lit.solid(standard('#f67318', '#f67318', 1.1, 0.4, 0));
  const discs = colors.map((color, index) => {
    const disc = new Group();
    const body = new Mesh(new CylinderGeometry(1.55, 1.55, 0.32, 56), lit.solid(standard(color, '#f67318', 0.07, 0.4, 0.08)));
    const rim = new Mesh(new TorusGeometry(1.55, 0.045, 8, 72), rimMaterial);
    rim.rotation.x = Math.PI / 2;
    rim.position.y = 0.16;
    const notch = new Mesh(new BoxGeometry(0.34, 0.14, 0.5), rimMaterial);
    notch.position.set(1.55, 0, 0);
    disc.add(body, rim, notch);
    disc.position.y = 0.4 + index * 0.66;
    group.add(disc);
    return disc;
  });
  const glow = glowSprite(lit, assets.glow, '#ff9a4d', 4.4, 0.35);
  glow.position.y = 1.2;
  group.add(glow);

  let phase = 0;
  return {
    group,
    hitRadius: 2.0,
    hitY: 1.1,
    update(frame) {
      lit.apply(frame.energy, frame.emphasis * 0.5 + frame.active * 0.5);
      phase += frame.dt;
      discs.forEach((disc, index) => {
        disc.rotation.y = phase * (0.3 + index * 0.1) * (index % 2 === 0 ? 1 : -1);
        disc.position.y = 0.4 + index * (0.66 + frame.active * 0.1);
      });
      glow.scale.setScalar(4.4 * (0.95 + frame.active * 0.22 + Math.sin(phase * 1.6) * 0.03));
    },
  };
}

function buildBolt(assets: VisualAssets, lit: Lit): NodeVisual {
  const group = new Group();
  const base = new Mesh(new CylinderGeometry(1.4, 1.55, 0.3, 6), lit.solid(standard('#14503c', '#2fb585', 0.3, 0.5, 0.2)));
  base.position.y = 0.15;
  const baseRing = new Mesh(new TorusGeometry(1.15, 0.035, 8, 6), lit.solid(standard('#7ff0c6', '#7ff0c6', 1.2, 0.4, 0)));
  baseRing.rotation.x = Math.PI / 2;
  baseRing.position.y = 0.32;
  group.add(base, baseRing);

  const shape = new Shape();
  shape.moveTo(0.25, 1.0);
  shape.lineTo(-0.55, -0.05);
  shape.lineTo(-0.08, -0.05);
  shape.lineTo(-0.3, -1.0);
  shape.lineTo(0.6, 0.18);
  shape.lineTo(0.12, 0.18);
  shape.lineTo(0.45, 1.0);
  shape.closePath();
  const geometry = new ExtrudeGeometry(shape, { depth: 0.34, bevelEnabled: true, bevelThickness: 0.06, bevelSize: 0.05, bevelSegments: 2 });
  geometry.center();
  const bolt = new Mesh(geometry, lit.solid(standard('#ffcc12', '#ffb000', 0.65, 0.3, 0.3)));
  bolt.scale.setScalar(1.1);
  bolt.position.y = 1.9;
  group.add(bolt);

  const glow = glowSprite(lit, assets.glow, '#ffcc12', 3.6, 0.5);
  glow.position.y = 1.9;
  group.add(glow);

  let phase = 0;
  let spin = 0;
  return {
    group,
    hitRadius: 1.7,
    hitY: 1.5,
    update(frame) {
      lit.apply(frame.energy, frame.emphasis * 0.5 + frame.active * 0.5);
      phase += frame.dt;
      spin += frame.dt * (0.7 + frame.active * 2.2);
      bolt.rotation.y = Math.sin(spin) * 0.7;
      bolt.position.y = 1.9 + Math.sin(phase * 1.6) * 0.09;
      glow.position.y = bolt.position.y;
      glow.scale.setScalar(3.6 * (0.95 + frame.active * 0.3));
    },
  };
}

function buildAnalyzer(assets: VisualAssets, lit: Lit): NodeVisual {
  const group = new Group();
  const center = new Group();
  center.position.y = 1.9;
  group.add(center);

  const core = new Mesh(new SphereGeometry(0.46, 32, 24), lit.solid(standard('#58d6a8', '#58d6a8', 1.15, 0.3, 0)));
  const shellGeometry = new IcosahedronGeometry(1.3, 1);
  const shell = new Mesh(shellGeometry, lit.glow(additive('#2fb585', 0.14)));
  const wire = new LineSegments(new EdgesGeometry(shellGeometry), lit.glow(new LineBasicMaterial({ color: '#8ff0cd', opacity: 0.9 })));
  center.add(core, shell, wire);

  const makeOrbit = (radius: number, tiltX: number, tiltZ: number, satellite: number, color: string) => {
    const tilt = new Group();
    tilt.rotation.set(tiltX, 0, tiltZ);
    const ring = new Mesh(new TorusGeometry(radius, 0.022, 8, 96), lit.glow(additive(color, 0.55)));
    const moon = new Mesh(new SphereGeometry(satellite, 20, 16), lit.solid(standard(color, color, 0.9, 0.3, 0)));
    tilt.add(ring, moon);
    center.add(tilt);
    return { moon, radius };
  };
  const modelOrbit = makeOrbit(1.95, 1.15, 0.2, 0.17, '#fefcf8');
  const outerOrbit = makeOrbit(2.3, 0.5, 0.95, 0.1, '#58d6a8');

  const scanRing = new Mesh(new TorusGeometry(1, 0.035, 8, 72), lit.glow(additive('#b5ffe4', 0.9)));
  scanRing.rotation.x = Math.PI / 2;
  const scanDisc = new Mesh(new CircleGeometry(1, 48), lit.glow(additive('#58d6a8', 0.2)));
  scanDisc.rotation.x = -Math.PI / 2;
  scanRing.visible = false;
  scanDisc.visible = false;
  center.add(scanRing, scanDisc);

  const glow = glowSprite(lit, assets.glow, '#58d6a8', 4.4, 0.4);
  center.add(glow);

  let phase = 0;
  let modelAngle = 0;
  let outerAngle = 2;
  return {
    group,
    hitRadius: 2.2,
    hitY: 1.9,
    setScan(progress) {
      const visible = progress !== null;
      scanRing.visible = visible;
      scanDisc.visible = visible;
      if (progress === null) return;
      // Two sweeps, top to bottom and back, over the progress.
      const swing = 0.5 + 0.5 * Math.sin(progress * Math.PI * 4 - Math.PI / 2);
      const y = -1.15 + swing * 2.3;
      const radius = Math.max(0.15, Math.sqrt(Math.max(0, 1.3 * 1.3 - y * y)));
      scanRing.position.y = y;
      scanDisc.position.y = y;
      scanRing.scale.setScalar(radius);
      scanDisc.scale.setScalar(radius);
    },
    update(frame) {
      lit.apply(frame.energy, frame.emphasis * 0.5 + frame.active * 0.5);
      const speed = 1 + frame.active * 1.8;
      phase += frame.dt;
      wire.rotation.y += frame.dt * 0.25 * speed;
      wire.rotation.x += frame.dt * 0.09 * speed;
      shell.rotation.copy(wire.rotation);
      modelAngle += frame.dt * 0.7 * speed;
      outerAngle -= frame.dt * 0.5 * speed;
      modelOrbit.moon.position.set(Math.cos(modelAngle) * modelOrbit.radius, Math.sin(modelAngle) * modelOrbit.radius, 0);
      outerOrbit.moon.position.set(Math.cos(outerAngle) * outerOrbit.radius, Math.sin(outerAngle) * outerOrbit.radius, 0);
      core.scale.setScalar(1 + Math.sin(phase * 2.2) * 0.07 + frame.active * 0.2);
      glow.scale.setScalar(4.4 * (0.95 + frame.active * 0.3));
    },
  };
}

function buildMonitor(assets: VisualAssets, lit: Lit): NodeVisual {
  const group = new Group();
  const metal = lit.solid(standard('#1a0a12', '#f67318', 0.14, 0.4, 0.5));
  const stand = new Mesh(new CylinderGeometry(0.1, 0.14, 0.9, 16), metal);
  stand.position.y = 0.5;
  const foot = new Mesh(new CylinderGeometry(0.7, 0.8, 0.08, 32), metal);
  foot.position.y = 0.04;
  group.add(stand, foot);

  const head = new Group();
  head.position.y = 1.95;
  head.rotation.x = -0.28;
  const frame = new Mesh(new BoxGeometry(3.2, 2.0, 0.14), metal);
  const screen = new Mesh(new PlaneGeometry(3.0, 1.82), lit.flat(new MeshBasicMaterial({ map: assets.screen, toneMapped: false })));
  screen.position.z = 0.08;
  const glow = glowSprite(lit, assets.glow, '#f67318', 5.2, 0.28);
  glow.position.z = -0.4;
  head.add(frame, screen, glow);
  group.add(head);

  let phase = 0;
  return {
    group,
    hitRadius: 2.1,
    hitY: 1.9,
    update(state) {
      lit.apply(state.energy, state.emphasis * 0.5 + state.active * 0.5);
      phase += state.dt;
      head.position.y = 1.95 + Math.sin(phase * 1.1) * 0.05;
      head.rotation.x = -0.28 + state.active * 0.05;
      glow.scale.setScalar(5.2 * (0.95 + state.active * 0.25));
    },
  };
}

function buildPerson(assets: VisualAssets, lit: Lit): NodeVisual {
  const group = new Group();
  const skin = lit.solid(standard('#fefcf8', '#ffcc12', 0.12, 0.45, 0.05));
  const figure = new Group();
  const body = new Mesh(new CapsuleGeometry(0.36, 0.6, 8, 24), skin);
  body.position.y = 0.75;
  const head = new Mesh(new SphereGeometry(0.3, 28, 20), skin);
  head.position.y = 1.62;
  figure.add(body, head);
  group.add(figure);

  const halo = new Mesh(new TorusGeometry(0.46, 0.05, 12, 48), lit.solid(standard('#ffcc12', '#ffcc12', 1.2, 0.3, 0)));
  halo.rotation.x = Math.PI / 2;
  halo.position.y = 2.2;
  group.add(halo);

  const glow = glowSprite(lit, assets.glow, '#ffcc12', 3.0, 0.3);
  glow.position.y = 1.3;
  group.add(glow);

  let phase = 0;
  return {
    group,
    hitRadius: 1.3,
    hitY: 1.2,
    update(frame) {
      lit.apply(frame.energy, frame.emphasis * 0.5 + frame.active * 0.5);
      phase += frame.dt;
      figure.rotation.y = Math.sin(phase * 0.5) * 0.35;
      halo.position.y = 2.2 + Math.sin(phase * 1.8) * 0.05 + frame.active * 0.1;
      halo.rotation.z = phase * 0.8;
      glow.scale.setScalar(3.0 * (0.95 + frame.active * 0.35));
    },
  };
}

export function buildVisual(kind: NodeKind, assets: VisualAssets): NodeVisual {
  const lit = new Lit();
  switch (kind) {
    case 'library':
      return buildLibrary(assets, lit);
    case 'flow':
      return buildFlow(assets, lit, false);
    case 'flow-double':
      return buildFlow(assets, lit, true);
    case 'tables':
      return buildTables(assets, lit);
    case 'bolt':
      return buildBolt(assets, lit);
    case 'analyzer':
      return buildAnalyzer(assets, lit);
    case 'monitor':
      return buildMonitor(assets, lit);
    case 'person':
      return buildPerson(assets, lit);
  }
}
