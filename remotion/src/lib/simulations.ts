/** Pure-math 2D/3D educational simulations (no Blender physics). */

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export function projectilePosition(
  t: number,
  u = 20,
  thetaDeg = 45,
  g = 9.8
): Vec3 {
  const theta = (thetaDeg * Math.PI) / 180;
  const x = u * Math.cos(theta) * t;
  const y = Math.max(0, u * Math.sin(theta) * t - 0.5 * g * t * t);
  return { x, y, z: 0 };
}

export function projectileRange(u = 20, thetaDeg = 45, g = 9.8): number {
  const theta = (thetaDeg * Math.PI) / 180;
  return (u * u * Math.sin(2 * theta)) / g;
}

export function projectileTimeOfFlight(u = 20, thetaDeg = 45, g = 9.8): number {
  const theta = (thetaDeg * Math.PI) / 180;
  return (2 * u * Math.sin(theta)) / g;
}

export function trajectoryPoints(
  u = 20,
  thetaDeg = 45,
  g = 9.8,
  samples = 48
): Vec3[] {
  const T = projectileTimeOfFlight(u, thetaDeg, g);
  const pts: Vec3[] = [];
  for (let i = 0; i <= samples; i++) {
    pts.push(projectilePosition((T * i) / samples, u, thetaDeg, g));
  }
  return pts;
}

export function freeFallY(t: number, h0 = 20, g = 9.8): number {
  return Math.max(0, h0 - 0.5 * g * t * t);
}

export function shmX(t: number, A = 2, omega = 2): number {
  return A * Math.cos(omega * t);
}

export function circularPosition(t: number, r = 2, omega = 1.5): Vec3 {
  return { x: r * Math.cos(omega * t), y: r * Math.sin(omega * t), z: 0 };
}

export function waveY(x: number, t: number, A = 1, k = 1.2, omega = 2): number {
  return A * Math.sin(k * x - omega * t);
}
