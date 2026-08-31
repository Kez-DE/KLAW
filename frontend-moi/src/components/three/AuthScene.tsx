import { Canvas, useFrame } from "@react-three/fiber";
import { Float } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";

const PAPER = "#FFFFFF";
const BRASS = "#E7C784";
const SKY = "#BFD9F2";
const MINT = "#A8D8C8";

/** Tờ văn bản lơ lửng — mỏng, sáng, bo nhẹ. */
function Sheets({ frozen }: { frozen: boolean }) {
  const group = useRef<THREE.Group>(null);

  const items = useMemo(
    () =>
      Array.from({ length: 14 }, (_, i) => {
        const a = (i / 14) * Math.PI * 2;
        const r = 4.2 + (i % 3) * 0.5;
        return {
          key: i,
          pos: [Math.cos(a) * r, -2.4 + (i / 14) * 5.2, Math.sin(a) * r] as const,
          rot: [0.22 * Math.sin(i), a + Math.PI / 2, 0.14 * Math.cos(i)] as const,
          tint: i % 4 === 0 ? SKY : i % 5 === 0 ? MINT : PAPER,
        };
      }),
    [],
  );

  useFrame((state, delta) => {
    if (frozen || !group.current) return;
    const dt = Math.min(delta, 0.05);
    group.current.rotation.y += dt * 0.09;
    const t = state.clock.elapsedTime;
    group.current.children.forEach((child, i) => {
      child.position.y += Math.sin(t * 0.5 + i) * 0.0016;
    });
  });

  return (
    <group ref={group}>
      {items.map((it) => (
        <group key={it.key} position={it.pos} rotation={it.rot}>
          <mesh>
            <boxGeometry args={[0.95, 1.32, 0.03]} />
            <meshStandardMaterial
              color={it.tint}
              roughness={0.5}
              metalness={0.02}
              emissive="#FFFFFF"
              emissiveIntensity={0.25}
              side={THREE.DoubleSide}
              transparent
              opacity={0.8}
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}

/** Cán cân công lý cách điệu, đung đưa nhẹ. */
function Scales({ frozen }: { frozen: boolean }) {
  const ref = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (frozen || !ref.current) return;
    ref.current.rotation.z = Math.sin(state.clock.elapsedTime * 0.6) * 0.08;
  });
  const brass = useMemo(
    () => new THREE.MeshStandardMaterial({ color: BRASS, metalness: 0.9, roughness: 0.22 }),
    [],
  );
  return (
    <group position={[0, 0.2, 0]} scale={0.95}>
      <group ref={ref}>
        <mesh material={brass}>
          <cylinderGeometry args={[0.045, 0.045, 3.1, 12]} />
        </mesh>
        <mesh position={[0, 1.25, 0]} rotation={[0, 0, Math.PI / 2]} material={brass}>
          <cylinderGeometry args={[0.038, 0.038, 3.0, 12]} />
        </mesh>
        {[-1.5, 1.5].map((x) => (
          <mesh key={x} position={[x, 0.85, 0]} material={brass}>
            <torusGeometry args={[0.42, 0.035, 10, 40]} />
          </mesh>
        ))}
        <mesh position={[0, 1.5, 0]} material={brass}>
          <sphereGeometry args={[0.13, 20, 20]} />
        </mesh>
      </group>
    </group>
  );
}

/** Bụi sáng lấp lánh bay lên. */
function Motes({ frozen }: { frozen: boolean }) {
  const ref = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const arr = new Float32Array(500 * 3);
    for (let i = 0; i < 500; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 14;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 10;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 10;
    }
    return arr;
  }, []);

  useFrame((_, delta) => {
    if (frozen || !ref.current) return;
    const dt = Math.min(delta, 0.05);
    const attr = ref.current.geometry.getAttribute("position") as THREE.BufferAttribute;
    for (let i = 0; i < attr.count; i++) {
      let y = attr.getY(i) + dt * 0.16;
      if (y > 5) y = -5;
      attr.setY(i, y);
    }
    attr.needsUpdate = true;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.035} color={BRASS} transparent opacity={0.5} />
    </points>
  );
}

function Parallax({ frozen }: { frozen: boolean }) {
  useFrame((state, delta) => {
    if (frozen) return;
    const k = 1 - Math.exp(-2.5 * Math.min(delta, 0.05));
    state.camera.position.x += (state.pointer.x * 0.7 - state.camera.position.x) * k;
    state.camera.position.y += (state.pointer.y * 0.45 - state.camera.position.y) * k;
    state.camera.lookAt(0, 0, 0);
  });
  return null;
}

export default function AuthScene() {
  const frozen =
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  return (
    <Canvas
      camera={{ position: [0, 0, 13], fov: 48 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: true }}
      style={{ position: "absolute", inset: 0 }}
    >
      <ambientLight intensity={1.15} />
      <directionalLight position={[6, 8, 6]} intensity={1.5} color="#FFF3DC" />
      <directionalLight position={[-7, -2, -4]} intensity={0.8} color="#BFD9F2" />
      <directionalLight position={[0, -4, -8]} intensity={0.6} color="#FFFFFF" />
      <Float speed={frozen ? 0 : 1.1} rotationIntensity={0.25} floatIntensity={0.5}>
        <Scales frozen={frozen} />
      </Float>
      <Sheets frozen={frozen} />
      <Motes frozen={frozen} />
      <Parallax frozen={frozen} />
    </Canvas>
  );
}
