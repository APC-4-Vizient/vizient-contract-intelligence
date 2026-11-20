import type { PerspectiveCamera } from 'three';
import { clamp, damp, poseToPosition } from './math';
import type { CameraPose } from './math';

/*
  A small orbit rig instead of OrbitControls. The story (a step, a selected part, the overview) decides a base pose,
  and the viewer's own dragging and zooming are offsets on top of it. That keeps the camera easy to steer by hand
  without ever losing track of where the story wants it.
*/

const USER_AZIMUTH_LIMIT = 0.85;
const POLAR_MIN = 0.45;
const POLAR_MAX = 1.35;
export const ZOOM_MIN = 0.55;
export const ZOOM_MAX = 1.45;

export class CameraRig {
  private readonly camera: PerspectiveCamera;
  private base: CameraPose;
  private current: CameraPose;
  private goal: CameraPose;
  private userAzimuth = 0;
  private userPolar = 0;
  private zoom = 1;
  private readonly position = { x: 0, y: 0, z: 0 };

  constructor(camera: PerspectiveCamera, pose: CameraPose) {
    this.camera = camera;
    this.base = { ...pose };
    this.current = { ...pose };
    this.goal = { ...pose };
    this.apply();
  }

  /** Aim the story's camera at a new pose. `keepUser` keeps the viewer's own rotation and zoom (used on resize). */
  setBase(pose: CameraPose, options: { instant: boolean; keepUser: boolean }): void {
    this.base = { ...pose };
    if (!options.keepUser) {
      this.userAzimuth = 0;
      this.userPolar = 0;
      this.zoom = 1;
    }
    this.goal = this.computeGoal(0);
    if (options.instant) {
      this.current = { ...this.goal };
      this.apply();
    }
  }

  drag(deltaAzimuth: number, deltaPolar: number): void {
    this.userAzimuth = clamp(this.userAzimuth + deltaAzimuth, -USER_AZIMUTH_LIMIT, USER_AZIMUTH_LIMIT);
    this.userPolar = clamp(this.userPolar + deltaPolar, POLAR_MIN - this.base.polar, POLAR_MAX - this.base.polar);
  }

  zoomBy(factor: number): void {
    this.zoom = clamp(this.zoom * factor, ZOOM_MIN, ZOOM_MAX);
  }

  /** Give the camera back to the story. */
  resetUser(): void {
    this.userAzimuth = 0;
    this.userPolar = 0;
    this.zoom = 1;
  }

  /** Move toward the goal. Returns true while the camera is still moving. */
  update(dt: number, sway: number | null, rate = 4.2): boolean {
    this.goal = this.computeGoal(sway === null ? 0 : Math.sin(sway * 0.32) * 0.045);
    const k = damp(rate, dt);
    const before = this.current;
    const next: CameraPose = {
      tx: before.tx + (this.goal.tx - before.tx) * k,
      ty: before.ty + (this.goal.ty - before.ty) * k,
      tz: before.tz + (this.goal.tz - before.tz) * k,
      azimuth: before.azimuth + (this.goal.azimuth - before.azimuth) * k,
      polar: before.polar + (this.goal.polar - before.polar) * k,
      distance: before.distance + (this.goal.distance - before.distance) * k,
    };
    const moving =
      Math.abs(this.goal.tx - next.tx) > 0.004 ||
      Math.abs(this.goal.ty - next.ty) > 0.004 ||
      Math.abs(this.goal.tz - next.tz) > 0.004 ||
      Math.abs(this.goal.azimuth - next.azimuth) > 0.0004 ||
      Math.abs(this.goal.polar - next.polar) > 0.0004 ||
      Math.abs(this.goal.distance - next.distance) > 0.01;
    this.current = next;
    this.apply();
    return moving || sway !== null;
  }

  private computeGoal(swayAzimuth: number): CameraPose {
    return {
      tx: this.base.tx,
      ty: this.base.ty,
      tz: this.base.tz,
      azimuth: this.base.azimuth + this.userAzimuth + swayAzimuth,
      polar: clamp(this.base.polar + this.userPolar, POLAR_MIN, POLAR_MAX),
      distance: this.base.distance * this.zoom,
    };
  }

  private apply(): void {
    poseToPosition(this.current, this.position);
    this.camera.position.set(this.position.x, this.position.y, this.position.z);
    this.camera.lookAt(this.current.tx, this.current.ty, this.current.tz);
  }
}
