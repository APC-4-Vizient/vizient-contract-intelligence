/* Small, pure helpers for the 3D view. They hold no three.js objects, so they run (and are tested) without WebGL. */

export interface Point3 {
  x: number;
  y: number;
  z: number;
}

export const clamp = (value: number, low: number, high: number): number => Math.min(high, Math.max(low, value));

export const lerp = (from: number, to: number, amount: number): number => from + (to - from) * amount;

export function smoothstep(edge0: number, edge1: number, value: number): number {
  const t = clamp((value - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

export const easeOutCubic = (t: number): number => 1 - Math.pow(1 - clamp(t, 0, 1), 3);

export function easeInOutCubic(t: number): number {
  const x = clamp(t, 0, 1);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}

/**
 * How far to move toward a goal this frame so that the motion looks the same at any frame rate.
 * `rate` is roughly "1 / seconds to settle".
 */
export const damp = (rate: number, dt: number): number => 1 - Math.exp(-rate * Math.max(0, dt));

export interface CameraPose {
  tx: number;
  ty: number;
  tz: number;
  /** Rotation around the vertical axis, in radians. 0 looks from the front. */
  azimuth: number;
  /** Angle from straight up, in radians. Smaller is more top-down. */
  polar: number;
  distance: number;
}

/** Distance at which a flat area of `width` x `height` world units fills the view of a camera. */
export function fitDistance(width: number, height: number, fovDeg: number, aspect: number): number {
  const half = Math.tan((fovDeg * Math.PI) / 360);
  return Math.max(width / (2 * half * Math.max(aspect, 0.1)), height / (2 * half));
}

export interface FrameOptions {
  fovDeg: number;
  aspect: number;
  polar: number;
  azimuth: number;
  /** Margin added on each side of the points, in world units. */
  padX: number;
  padZ: number;
  /** The view never gets closer than this width, so a single node is not shown at a silly size. */
  minWidth: number;
  /** Height above the floor that must stay in view, so labels above the nodes are not cut off. */
  heightY: number;
  targetY: number;
}

/** A camera pose that keeps the points (and the labels above them) in view. */
export function framePoints(points: readonly (readonly [number, number, number])[], options: FrameOptions): CameraPose {
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  for (const [x, , z] of points) {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minZ = Math.min(minZ, z);
    maxZ = Math.max(maxZ, z);
  }
  if (!Number.isFinite(minX)) {
    minX = maxX = minZ = maxZ = 0;
  }
  const width = Math.max(maxX - minX + options.padX * 2, options.minWidth);
  const depth = maxZ - minZ + options.padZ * 2;
  // A depth step on the floor shows up as cos(polar) of its length on screen, a height step as sin(polar).
  const height = depth * Math.cos(options.polar) + options.heightY * Math.sin(options.polar);
  return {
    tx: (minX + maxX) / 2,
    ty: options.targetY,
    tz: (minZ + maxZ) / 2,
    azimuth: options.azimuth,
    polar: options.polar,
    // Things nearer the camera look bigger, so leave a little room.
    distance: fitDistance(width, height, options.fovDeg, options.aspect) * 1.08,
  };
}

/** The camera's position for a pose. */
export function poseToPosition(pose: CameraPose, out: Point3 = { x: 0, y: 0, z: 0 }): Point3 {
  const flat = Math.sin(pose.polar) * pose.distance;
  out.x = pose.tx + flat * Math.sin(pose.azimuth);
  out.y = pose.ty + Math.cos(pose.polar) * pose.distance;
  out.z = pose.tz + flat * Math.cos(pose.azimuth);
  return out;
}

/** Where `progress` (0 to 1) falls along a path made of several hops of the given lengths. */
export function locateAlong(lengths: readonly number[], progress: number): { index: number; local: number } {
  if (lengths.length === 0) return { index: 0, local: 0 };
  const total = lengths.reduce((sum, length) => sum + length, 0);
  if (total <= 0) return { index: 0, local: clamp(progress, 0, 1) };
  let remaining = clamp(progress, 0, 1) * total;
  for (let index = 0; index < lengths.length; index += 1) {
    if (remaining <= lengths[index] || index === lengths.length - 1) {
      return { index, local: lengths[index] === 0 ? 1 : clamp(remaining / lengths[index], 0, 1) };
    }
    remaining -= lengths[index];
  }
  return { index: lengths.length - 1, local: 1 };
}

/** The point `u` (0 to 1) of the way along a polyline whose points are roughly evenly spaced. */
export function samplePolyline(points: readonly Point3[], u: number, out: Point3 = { x: 0, y: 0, z: 0 }): Point3 {
  if (points.length === 0) return out;
  if (points.length === 1) return Object.assign(out, points[0]);
  const scaled = clamp(u, 0, 1) * (points.length - 1);
  const index = Math.min(Math.floor(scaled), points.length - 2);
  const local = scaled - index;
  const a = points[index];
  const b = points[index + 1];
  out.x = lerp(a.x, b.x, local);
  out.y = lerp(a.y, b.y, local);
  out.z = lerp(a.z, b.z, local);
  return out;
}

export function polylineLength(points: readonly Point3[]): number {
  let length = 0;
  for (let index = 1; index < points.length; index += 1) {
    length += Math.hypot(points[index].x - points[index - 1].x, points[index].y - points[index - 1].y, points[index].z - points[index - 1].z);
  }
  return length;
}
