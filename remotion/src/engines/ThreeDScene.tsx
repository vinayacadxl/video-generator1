import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import { Float } from "@react-three/drei";
import type { SceneClipProps } from "../lib/types";
import {
  projectilePosition,
  projectileRange,
  projectileTimeOfFlight,
  trajectoryPoints,
} from "../lib/simulations";
import { KineticText, SceneChrome } from "../components/primitives";

const STAGE_COLORS = ["#EF4444", "#3B82F6", "#22C55E", "#F59E0B", "#A78BFA", "#38BDF8"];

/** Ball-stick chain from TeachingDocument stages — uses Three.js + drei Float */
const TeachingMolecule3D: React.FC<{
  labels: string[];
  progress: number;
}> = ({ labels, progress }) => {
  const spin = progress * Math.PI * 2;
  const n = Math.max(2, Math.min(labels.length || 2, 6));
  const spacing = 1.15;
  const atoms = Array.from({ length: n }, (_, i) => ({
    x: (i - (n - 1) / 2) * spacing,
    color: STAGE_COLORS[i % STAGE_COLORS.length],
    label: labels[i] || `S${i + 1}`,
  }));
  return (
    <Float speed={1.4} rotationIntensity={0.35} floatIntensity={0.45}>
      <group rotation={[0.25, spin, 0.1]}>
        {atoms.map((a, i) => (
          <group key={i}>
            <mesh position={[a.x, 0, 0]}>
              <sphereGeometry args={[0.38, 28, 28]} />
              <meshStandardMaterial color={a.color} metalness={0.25} roughness={0.35} />
            </mesh>
            {i < atoms.length - 1 ? (
              <mesh position={[(a.x + atoms[i + 1].x) / 2, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
                <cylinderGeometry args={[0.07, 0.07, spacing * 0.85, 10]} />
                <meshStandardMaterial color="#CBD5E1" />
              </mesh>
            ) : null}
          </group>
        ))}
      </group>
    </Float>
  );
};

const TrajectoryRibbon: React.FC<{
  progress: number;
  u?: number;
  theta?: number;
  g?: number;
}> = ({ progress, u = 20, theta = 45, g = 9.8 }) => {
  const pts = useMemo(() => trajectoryPoints(u, theta, g, 64), [u, theta, g]);
  const T = projectileTimeOfFlight(u, theta, g);
  const ball = projectilePosition(progress * T, u, theta, g);
  const range = projectileRange(u, theta, g);
  const scale = 0.18;

  return (
    <group position={[-range * scale * 0.45, -1.2, 0]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[range * scale * 0.5, 0, 0]}>
        <planeGeometry args={[range * scale + 2, 6]} />
        <meshStandardMaterial color="#0F172A" />
      </mesh>

      <mesh position={[range * scale * 0.5, 0.02, 0]}>
        <boxGeometry args={[range * scale, 0.03, 0.03]} />
        <meshStandardMaterial color="#475569" />
      </mesh>
      <mesh position={[0, 1.2, 0]}>
        <boxGeometry args={[0.03, 2.4, 0.03]} />
        <meshStandardMaterial color="#475569" />
      </mesh>

      {pts.map((p, i) => {
        if (i / pts.length > progress) return null;
        return (
          <mesh key={i} position={[p.x * scale, p.y * scale, 0]}>
            <sphereGeometry args={[0.04, 12, 12]} />
            <meshStandardMaterial color="#38BDF8" emissive="#0EA5E9" emissiveIntensity={0.4} />
          </mesh>
        );
      })}

      <mesh position={[ball.x * scale, ball.y * scale, 0]}>
        <sphereGeometry args={[0.16, 24, 24]} />
        <meshStandardMaterial color="#F59E0B" emissive="#B45309" emissiveIntensity={0.35} />
      </mesh>

      <group>
        <mesh position={[0.55, 0.05, 0]} rotation={[0, 0, -0.2]}>
          <cylinderGeometry args={[0.03, 0.03, 1.1, 8]} />
          <meshStandardMaterial color="#22D3EE" />
        </mesh>
        <mesh position={[0.05, 0.7, 0]}>
          <cylinderGeometry args={[0.03, 0.03, 1.1, 8]} />
          <meshStandardMaterial color="#F472B6" />
        </mesh>
        <mesh position={[ball.x * scale + 0.05, ball.y * scale - 0.55, 0]}>
          <cylinderGeometry args={[0.03, 0.03, 0.9, 8]} />
          <meshStandardMaterial color="#F87171" />
        </mesh>
      </group>
    </group>
  );
};

function detectSimulation(
  scene: SceneClipProps["scene"],
  topic?: string,
  title?: string,
  subject?: string,
  solutionType?: string
) {
  const blob = `${scene.narration} ${(scene.visuals || []).join(" ")} ${(scene.animations || []).join(" ")} ${topic || ""} ${title || ""} ${subject || ""} ${solutionType || ""}`.toLowerCase();
  // Never default chemistry / diagram lessons to projectile
  if (/diagram|radial|orbital|atomic|chemistry|rdf|graph/.test(blob)) return "molecule";
  if (/projectile|trajectory|thrown|range|parabola/.test(blob)) return "projectile";
  if (/train|car|brake|momentum/.test(blob)) return "vehicle";
  if (/molecule|atom|electron/.test(blob)) return "molecule";
  if (/earth|planet|orbit/.test(blob)) return "earth";
  if (/rocket|launch/.test(blob)) return "rocket";
  return "molecule";
}

const GenericObjectScene: React.FC<{
  kind: string;
  progress: number;
  u?: number;
  theta?: number;
  g?: number;
}> = ({ kind, progress, u = 20, theta = 45, g = 9.8 }) => {
  const spin = progress * Math.PI * 2;
  if (kind === "earth") {
    return (
      <mesh rotation={[0.4, spin, 0]}>
        <sphereGeometry args={[1.4, 48, 48]} />
        <meshStandardMaterial color="#2563EB" roughness={0.45} metalness={0.2} />
      </mesh>
    );
  }
  if (kind === "molecule") {
    return (
      <Float speed={1.2} rotationIntensity={0.3} floatIntensity={0.4}>
        <group rotation={[0.2, spin, 0]}>
          <mesh position={[-0.7, 0, 0]}>
            <sphereGeometry args={[0.45, 32, 32]} />
            <meshStandardMaterial color="#EF4444" />
          </mesh>
          <mesh position={[0.7, 0, 0]}>
            <sphereGeometry args={[0.45, 32, 32]} />
            <meshStandardMaterial color="#3B82F6" />
          </mesh>
          <mesh rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.08, 0.08, 1.4, 12]} />
            <meshStandardMaterial color="#CBD5E1" />
          </mesh>
        </group>
      </Float>
    );
  }
  if (kind === "rocket" || kind === "vehicle") {
    return (
      <group position={[interpolate(progress, [0, 1], [-2.2, 2.2]), 0, 0]}>
        <mesh>
          <boxGeometry args={[1.8, 0.55, 0.8]} />
          <meshStandardMaterial color={kind === "rocket" ? "#F8FAFC" : "#F97316"} />
        </mesh>
        <mesh position={[0.9, 0.15, 0]} rotation={[0, 0, Math.PI / 2]}>
          <coneGeometry args={[0.28, 0.7, 16]} />
          <meshStandardMaterial color="#EF4444" />
        </mesh>
      </group>
    );
  }
  // ONLY true projectile — never default unknown kinds (fluid/wave/…) to the first demo arc
  if (kind === "projectile") {
    return <TrajectoryRibbon progress={progress} u={u} theta={theta} g={g} />;
  }
  // Neutral placeholder so wrong routing is obvious in preview (not a fake projectile)
  return (
    <Float speed={1} rotationIntensity={0.2} floatIntensity={0.3}>
      <mesh rotation={[0.3, progress * Math.PI, 0]}>
        <boxGeometry args={[1.4, 1.4, 1.4]} />
        <meshStandardMaterial color="#64748B" wireframe />
      </mesh>
    </Float>
  );
};

export const ThreeDScene: React.FC<SceneClipProps> = (props) => {
  const { scene, solution, title, subject, topic } = props;
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateRight: "clamp",
  });
  const simFromSolution = String(solution?.simulation?.type || "").toLowerCase();
  const stageLabels = useMemo(() => {
    const td = solution?.teachingDocument;
    const stages = (td?.stages || []).filter((s) => String(s.role || "") !== "option");
    return stages.map((s) => String(s.label || s.id || "")).filter(Boolean).slice(0, 6);
  }, [solution?.teachingDocument]);
  const useTeachingMol =
    stageLabels.length >= 2 ||
    String((scene as { engine?: string }).engine || "") === "threejs" ||
    Boolean((scene as { force3D?: boolean }).force3D);

  const sim =
    useTeachingMol && stageLabels.length >= 1
      ? "teaching_molecule"
      : simFromSolution && !["none", "diagram", "pe_curve", ""].includes(simFromSolution)
        ? simFromSolution === "projectile" &&
          /chem|atomic|orbital|radial/i.test(`${subject} ${topic} ${solution?.concept}`)
          ? "molecule"
          : simFromSolution
        : detectSimulation(scene, topic, title, subject, solution?.concept);
  const params = solution?.simulation?.params || {};
  const u = Number(params.u ?? 20);
  const theta = Number(params.theta ?? 45);
  const g = Number(params.g ?? 9.8);
  const camZ = interpolate(progress, [0, 1], [6.2, 5.2]);
  const displayTitle = scene.onScreen?.title || title || topic || "3D Concept";

  return (
    <SceneChrome subject={subject} topic={topic || title} sceneType={String(scene.type)}>
      <AbsoluteFill style={{ paddingTop: 96 }}>
        <div style={{ paddingLeft: 56, paddingRight: 56 }}>
          <KineticText
            text={displayTitle}
            style={{ fontSize: 42, fontWeight: 800, color: "#F8FAFC" }}
          />
          <KineticText
            delay={6}
            text={
              scene.onScreen?.subtitle ||
              scene.learningGoal ||
              scene.narration?.slice(0, 140) ||
              "Watch the spatial model."
            }
            style={{ fontSize: 22, color: "#94A3B8", marginTop: 10, maxWidth: 1000 }}
          />
        </div>
        <AbsoluteFill style={{ top: 170 }}>
          <ThreeCanvas
            width={width}
            height={height - 170}
            camera={{ position: [0, 1.4, camZ], fov: 42 }}
            style={{ background: "transparent" }}
          >
            <ambientLight intensity={0.65} />
            <directionalLight position={[4, 6, 3]} intensity={1.2} />
            <pointLight position={[-3, 2, 2]} intensity={0.5} color="#38BDF8" />
            {sim === "teaching_molecule" ? (
              <TeachingMolecule3D
                labels={stageLabels.length ? stageLabels : ["A", "B"]}
                progress={Math.min(1, progress * 1.05)}
              />
            ) : (
              <GenericObjectScene
                kind={sim}
                progress={Math.min(1, progress * 1.05)}
                u={u}
                theta={theta}
                g={g}
              />
            )}
          </ThreeCanvas>
        </AbsoluteFill>
      </AbsoluteFill>
    </SceneChrome>
  );
};
