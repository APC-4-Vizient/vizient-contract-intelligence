import {
  AdditiveBlending,
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  CatmullRomCurve3,
  Color,
  ConeGeometry,
  CylinderGeometry,
  DoubleSide,
  EdgesGeometry,
  Group,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PlaneGeometry,
  Points,
  PointsMaterial,
  RingGeometry,
  ShaderMaterial,
  TorusGeometry,
  TubeGeometry,
  Vector2,
  Vector3,
} from 'three';
import type { Texture } from 'three';
import { ZONES, resolveRoute } from '../architecture';
import type { ArchEdge, ArchNode, EdgeTone, NodeKind } from '../architecture';
import { samplePolyline } from './math';

/** The floor of the scene: a faint grid that fades out with distance, and a ring that can ripple out from a point. */
const FLOOR_VERTEX = /* glsl */ `
  varying vec3 vWorld;
  void main() {
    vec4 world = modelMatrix * vec4(position, 1.0);
    vWorld = world.xyz;
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`;

const FLOOR_FRAGMENT = /* glsl */ `
  uniform vec3 uLine;
  uniform vec3 uPingColor;
  uniform vec2 uPingCenter;
  uniform float uPingRadius;
  uniform float uPingAlpha;
  varying vec3 vWorld;

  float gridLine(vec2 p, float size, float width) {
    vec2 q = p / size;
    vec2 g = abs(fract(q - 0.5) - 0.5) / max(fwidth(q), vec2(0.0001));
    return 1.0 - clamp(min(g.x, g.y) / width, 0.0, 1.0);
  }

  void main() {
    vec2 p = vWorld.xz;
    float minor = gridLine(p, 1.0, 1.0) * 0.3;
    float major = gridLine(p, 5.0, 1.3) * 0.6;
    float fade = 1.0 - smoothstep(10.0, 38.0, length(p - vec2(0.0, 2.5)));
    float lines = max(minor, major) * fade;
    float ring = (1.0 - smoothstep(0.0, 1.1, abs(length(p - uPingCenter) - uPingRadius))) * uPingAlpha;
    vec3 color = mix(uLine, uPingColor, clamp(ring * 1.4, 0.0, 1.0));
    gl_FragColor = vec4(color, clamp(lines * 0.36 + ring * 0.6, 0.0, 1.0));
    #include <colorspace_fragment>
  }
`;

const PING_SPEED = 10;
const PING_REACH = 9;

export interface FloorVisual {
  mesh: Mesh;
  /** Start a ring that ripples out over the floor from a point. */
  ping(x: number, z: number, color: string): void;
  /** Advance the ring. Returns true while it is still showing. */
  update(dt: number): boolean;
}

export function buildFloor(): FloorVisual {
  const uniforms = {
    uLine: { value: new Color('#cfc0c8') },
    uPingColor: { value: new Color('#ff9a4d') },
    uPingCenter: { value: new Vector2(0, 0) },
    uPingRadius: { value: 0 },
    uPingAlpha: { value: 0 },
  };
  const material = new ShaderMaterial({
    uniforms,
    vertexShader: FLOOR_VERTEX,
    fragmentShader: FLOOR_FRAGMENT,
    transparent: true,
    depthWrite: false,
  });
  const mesh = new Mesh(new PlaneGeometry(140, 90), material);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.set(0, -0.17, 2.5);
  mesh.renderOrder = -2;

  let radius = -1;
  return {
    mesh,
    ping(x, z, color) {
      uniforms.uPingCenter.value.set(x, z);
      uniforms.uPingColor.value.set(color);
      radius = 0.4;
      uniforms.uPingRadius.value = radius;
      uniforms.uPingAlpha.value = 1;
    },
    update(dt) {
      if (radius < 0) return false;
      radius += dt * PING_SPEED;
      if (radius >= PING_REACH) {
        radius = -1;
        uniforms.uPingAlpha.value = 0;
        return false;
      }
      uniforms.uPingRadius.value = radius;
      uniforms.uPingAlpha.value = (1 - radius / PING_REACH) ** 1.5;
      return true;
    },
  };
}

/** The tinted slabs that mark Microsoft 365, Power Platform, Azure and the people. */
export function buildZones(): Group {
  const group = new Group();
  for (const zone of ZONES) {
    const tint = new Color(zone.color);
    for (const slab of zone.slabs) {
      const geometry = new BoxGeometry(slab.width, 0.16, slab.depth);
      const body = new Mesh(
        geometry,
        new MeshStandardMaterial({
          color: tint.clone().multiplyScalar(0.26),
          emissive: tint,
          emissiveIntensity: 0.1,
          roughness: 0.9,
          metalness: 0,
          transparent: true,
          opacity: 0.94,
        }),
      );
      body.position.set(slab.x, -0.08, slab.z);
      const outline = new LineSegments(new EdgesGeometry(geometry), new LineBasicMaterial({ color: tint, transparent: true, opacity: 0.9 }));
      outline.position.copy(body.position);
      group.add(body, outline);
    }
  }
  return group;
}

export const PAD_RADIUS: Record<NodeKind, number> = {
  library: 2.0,
  flow: 1.7,
  'flow-double': 1.7,
  tables: 2.0,
  bolt: 1.8,
  analyzer: 2.1,
  monitor: 2.1,
  person: 1.5,
};

export interface PadVisual {
  group: Group;
  update(energy: number, emphasis: number, time: number): void;
}

/** The round plinth each part stands on, with a glowing rim that brightens with the part. */
export function buildPad(node: ArchNode): PadVisual {
  const radius = PAD_RADIUS[node.kind];
  const group = new Group();
  group.position.set(node.position[0], 0, node.position[2]);

  const bodyMaterial = new MeshStandardMaterial({ color: '#3a1a28', emissive: node.color, emissiveIntensity: 0.05, roughness: 0.6, metalness: 0.1 });
  const body = new Mesh(new CylinderGeometry(radius, radius + 0.1, 0.12, 72), bodyMaterial);
  body.position.y = 0.06;

  const rimMaterial = new MeshBasicMaterial({ color: node.color, transparent: true, opacity: 0.5, blending: AdditiveBlending, depthWrite: false });
  const rim = new Mesh(new TorusGeometry(radius - 0.04, 0.03, 8, 96), rimMaterial);
  rim.rotation.x = Math.PI / 2;
  rim.position.y = 0.125;

  const focusMaterial = new MeshBasicMaterial({ color: '#fefcf8', transparent: true, opacity: 0, blending: AdditiveBlending, depthWrite: false, side: DoubleSide });
  const focus = new Mesh(new RingGeometry(radius + 0.16, radius + 0.3, 96), focusMaterial);
  focus.rotation.x = -Math.PI / 2;
  focus.position.y = 0.04;

  group.add(body, rim, focus);
  return {
    group,
    update(energy, emphasis, time) {
      bodyMaterial.emissiveIntensity = 0.04 + 0.22 * energy;
      rimMaterial.opacity = 0.16 + 0.74 * energy;
      focusMaterial.opacity = emphasis * (0.62 + 0.2 * Math.sin(time * 3.2));
    },
  };
}

const TONE: Record<EdgeTone, string> = { forward: '#ff9a4d', return: '#5fe0b2', review: '#ffcc12' };
const UP = new Vector3(0, 1, 0);
const ARROW_LENGTH = 0.46;

export interface EdgeVisual {
  group: Group;
  /** Evenly spaced points along the route, used by the contract tile and the finding chips. */
  path: Vector3[];
  length: number;
  midpoint: Vector3;
  update(dt: number, energy: number): void;
}

function arrowHead(curve: CatmullRomCurve3, length: number, atEnd: boolean, material: MeshBasicMaterial): Mesh {
  const at = Math.min(0.5, (ARROW_LENGTH * 0.65) / length);
  const u = atEnd ? 1 - at : at;
  const tangent = curve.getTangentAt(u);
  if (!atEnd) tangent.negate();
  const cone = new Mesh(new ConeGeometry(0.17, ARROW_LENGTH, 14), material);
  cone.position.copy(curve.getPointAt(u));
  cone.quaternion.setFromUnitVectors(UP, tangent);
  return cone;
}

/** A glowing wire between two parts, with sparks that stream along it. They speed up and brighten when the edge is lit. */
export function buildEdge(edge: ArchEdge, glow: Texture): EdgeVisual {
  const tone = new Color(TONE[edge.tone]);
  const curve = new CatmullRomCurve3(
    resolveRoute(edge).map(([x, y, z]) => new Vector3(x, y, z)),
    false,
    'centripetal',
  );
  const length = curve.getLength();
  const path = curve.getSpacedPoints(Math.max(48, Math.ceil(length * 8)));
  const segments = Math.max(24, Math.ceil(length * 6));
  const group = new Group();

  const coreMaterial = new MeshBasicMaterial({ color: tone, transparent: true, opacity: 0.3 });
  const haloMaterial = new MeshBasicMaterial({ color: tone, transparent: true, opacity: 0, blending: AdditiveBlending, depthWrite: false });
  const arrowMaterial = new MeshBasicMaterial({ color: tone, transparent: true, opacity: 0.6 });
  group.add(
    new Mesh(new TubeGeometry(curve, segments, 0.04, 8, false), coreMaterial),
    new Mesh(new TubeGeometry(curve, segments, 0.17, 10, false), haloMaterial),
    arrowHead(curve, length, true, arrowMaterial),
  );
  if (edge.bidirectional) group.add(arrowHead(curve, length, false, arrowMaterial));

  const count = Math.max(6, Math.round(length * 1.6));
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const geometry = new BufferGeometry();
  const positionAttribute = new BufferAttribute(positions, 3);
  const colorAttribute = new BufferAttribute(colors, 3);
  geometry.setAttribute('position', positionAttribute);
  geometry.setAttribute('color', colorAttribute);
  const sparks = new Points(
    geometry,
    new PointsMaterial({ size: 0.46, map: glow, vertexColors: true, transparent: true, depthWrite: false, blending: AdditiveBlending, sizeAttenuation: true }),
  );
  sparks.frustumCulled = false;
  group.add(sparks);

  const point = new Vector3();
  let phase = 0;
  const lay = (): void => {
    for (let i = 0; i < count; i += 1) {
      const along = (phase + i / count) % 1;
      samplePolyline(path, edge.bidirectional && i % 2 === 1 ? 1 - along : along, point);
      positions[i * 3] = point.x;
      positions[i * 3 + 1] = point.y;
      positions[i * 3 + 2] = point.z;
    }
    positionAttribute.needsUpdate = true;
  };
  lay();

  return {
    group,
    path,
    length,
    midpoint: curve.getPointAt(0.5),
    update(dt, energy) {
      phase = (phase + (dt * (1.2 + 3.2 * energy)) / length) % 1;
      lay();
      const brightness = 0.2 + 0.8 * energy;
      for (let i = 0; i < count; i += 1) {
        const along = (phase + i / count) % 1;
        const fade = Math.sin(Math.PI * along) ** 0.6 * brightness;
        colors[i * 3] = tone.r * fade;
        colors[i * 3 + 1] = tone.g * fade;
        colors[i * 3 + 2] = tone.b * fade;
      }
      colorAttribute.needsUpdate = true;
      coreMaterial.opacity = 0.2 + 0.55 * energy;
      haloMaterial.opacity = 0.22 * Math.max(0, (energy - 0.4) / 0.6);
      arrowMaterial.opacity = 0.4 + 0.6 * energy;
    },
  };
}
