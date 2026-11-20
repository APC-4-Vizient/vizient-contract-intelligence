import { describe, expect, it } from 'vitest';
import {
  damp,
  easeInOutCubic,
  fitDistance,
  framePoints,
  locateAlong,
  poseToPosition,
  polylineLength,
  samplePolyline,
} from './math';

describe('easing and damping', () => {
  it('runs from 0 to 1 and is symmetric about the middle', () => {
    expect(easeInOutCubic(0)).toBe(0);
    expect(easeInOutCubic(1)).toBe(1);
    expect(easeInOutCubic(0.5)).toBeCloseTo(0.5, 10);
    expect(easeInOutCubic(-3)).toBe(0);
    expect(easeInOutCubic(7)).toBe(1);
  });

  it('moves further for a longer frame, never past the goal', () => {
    expect(damp(5, 0)).toBe(0);
    expect(damp(5, 0.016)).toBeLessThan(damp(5, 0.032));
    expect(damp(5, 100)).toBeLessThanOrEqual(1);
  });
});

describe('camera framing', () => {
  const base = { fovDeg: 36, aspect: 2, polar: 1, azimuth: 0, padX: 1, padZ: 1, minWidth: 10, heightY: 4, targetY: 1.5 };

  it('backs off as the content gets wider, and never closer than the minimum width', () => {
    const narrow = framePoints([[0, 0, 0]], base);
    const wide = framePoints(
      [
        [-15, 0, 0],
        [15, 0, 0],
      ],
      base,
    );
    expect(wide.distance).toBeGreaterThan(narrow.distance);
    expect(narrow.distance).toBeGreaterThanOrEqual(fitDistance(10, 0, 36, 2));
  });

  it('looks at the middle of the points', () => {
    const pose = framePoints(
      [
        [-4, 0, 2],
        [6, 0, 8],
      ],
      base,
    );
    expect(pose.tx).toBe(1);
    expect(pose.tz).toBe(5);
    expect(pose.ty).toBe(1.5);
  });

  it('needs more distance on a narrower view', () => {
    const points = [[0, 0, 0]] as const;
    expect(framePoints(points, { ...base, aspect: 1 }).distance).toBeGreaterThan(framePoints(points, { ...base, aspect: 2 }).distance);
  });

  it('places the camera in front of and above its target', () => {
    const position = poseToPosition({ tx: 0, ty: 0, tz: 0, azimuth: 0, polar: Math.PI / 4, distance: 10 });
    expect(position.x).toBeCloseTo(0, 10);
    expect(position.y).toBeCloseTo(7.071, 2);
    expect(position.z).toBeCloseTo(7.071, 2);
  });
});

describe('paths', () => {
  const line = [
    { x: 0, y: 0, z: 0 },
    { x: 2, y: 0, z: 0 },
    { x: 4, y: 2, z: 0 },
  ];

  it('samples a polyline from end to end', () => {
    expect(samplePolyline(line, 0)).toEqual(line[0]);
    expect(samplePolyline(line, 1)).toEqual(line[2]);
    expect(samplePolyline(line, 0.25)).toEqual({ x: 1, y: 0, z: 0 });
    expect(samplePolyline(line, 9)).toEqual(line[2]);
  });

  it('measures a polyline', () => {
    expect(polylineLength(line)).toBeCloseTo(2 + Math.hypot(2, 2), 10);
  });

  it('finds the hop and the place along it', () => {
    expect(locateAlong([2, 2], 0)).toEqual({ index: 0, local: 0 });
    expect(locateAlong([2, 2], 0.25)).toEqual({ index: 0, local: 0.5 });
    expect(locateAlong([2, 2], 0.75)).toEqual({ index: 1, local: 0.5 });
    expect(locateAlong([2, 6], 1)).toEqual({ index: 1, local: 1 });
    expect(locateAlong([], 0.5)).toEqual({ index: 0, local: 0 });
  });
});
