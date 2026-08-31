import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  Environment,
  Lightformer,
  Html,
  PresentationControls,
} from "@react-three/drei";
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import * as THREE from "three";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

/* ------------------------------------------------------------------ *
 * Data — real Vietnamese văn bản quy phạm pháp luật
 * ------------------------------------------------------------------ */

type Doc = {
  soHieu: string;
  ten: string;
  trangThai: "Còn hiệu lực" | "Sắp hiệu lực" | "Hết hiệu lực";
  trichDan: string;
  excerpt: string;
};

const DOCS: Doc[] = [
  {
    soHieu: "45/2019/QH14",
    ten: "Bộ luật Lao động 2019",
    trangThai: "Còn hiệu lực",
    trichDan: "Khoản 1 Điều 25 Bộ luật Lao động 2019",
    excerpt:
      "Thời gian thử việc không quá 180 ngày đối với công việc của người quản lý doanh nghiệp; không quá 60 ngày đối với công việc có chức danh nghề cần trình độ từ cao đẳng trở lên.",
  },
  {
    soHieu: "91/2015/QH13",
    ten: "Bộ luật Dân sự 2015",
    trangThai: "Còn hiệu lực",
    trichDan: "Khoản 1 Điều 468 Bộ luật Dân sự 2015",
    excerpt:
      "Lãi suất vay do các bên thỏa thuận nhưng không được vượt quá 20%/năm của khoản tiền vay, trừ trường hợp luật khác có liên quan quy định khác.",
  },
  {
    soHieu: "36/2005/QH11",
    ten: "Luật Thương mại 2005",
    trangThai: "Còn hiệu lực",
    trichDan: "Điều 301 Luật Thương mại 2005",
    excerpt:
      "Mức phạt đối với vi phạm nghĩa vụ hợp đồng do các bên thỏa thuận trong hợp đồng, nhưng không quá 8% giá trị phần nghĩa vụ hợp đồng bị vi phạm.",
  },
  {
    soHieu: "356/2025/NĐ-CP",
    ten: "Nghị định 356/2025/NĐ-CP",
    trangThai: "Sắp hiệu lực",
    trichDan: "Điều 4 Nghị định 356/2025/NĐ-CP",
    excerpt:
      "Văn bản điện tử được ký số hợp lệ có giá trị pháp lý như văn bản giấy và là căn cứ để các bên thực hiện quyền, nghĩa vụ theo hợp đồng.",
  },
];

const SLAB_COUNT = 14;

/* Label texture: JetBrains-Mono-style số hiệu drawn locally (no font fetch,
   full Vietnamese glyph support from the system stack). */
function makeLabelTexture(text: string) {
  const w = 512;
  const h = 728;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "rgba(200,164,92,0.30)";
  ctx.font =
    '600 46px "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace';
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, w / 2, h * 0.5);
  ctx.fillStyle = "rgba(200,164,92,0.16)";
  ctx.fillRect(w * 0.22, h * 0.56, w * 0.56, 3);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

/* ------------------------------------------------------------------ *
 * Shared resources — one geometry + one material for every slab
 * ------------------------------------------------------------------ */

function useSharedResources() {
  return useMemo(() => {
    const slabGeo = new THREE.BoxGeometry(1.4, 2.0, 0.06);
    const edgeGeo = new THREE.BoxGeometry(1.52, 2.12, 0.04);
    const labelGeo = new THREE.PlaneGeometry(1.32, 1.88);

    const slabMat = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color("#F7FBFF"),
      transmission: 0.72,
      roughness: 0.1,
      thickness: 0.45,
      ior: 1.35,
      metalness: 0,
      clearcoat: 0.6,
      clearcoatRoughness: 0.12,
      emissive: new THREE.Color("#DCE9FA"),
      emissiveIntensity: 0.16,
      transparent: true,
      opacity: 0.95,
      side: THREE.DoubleSide,
    });
    const edgeMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color("#E4BE72"),
      metalness: 0.85,
      roughness: 0.2,
      emissive: new THREE.Color("#E4BE72"),
      emissiveIntensity: 0.18,
    });
    const edgeHotMat = edgeMat.clone();
    edgeHotMat.emissiveIntensity = 0.85;

    return { slabGeo, edgeGeo, labelGeo, slabMat, edgeMat, edgeHotMat };
  }, []);
}

/* ------------------------------------------------------------------ *
 * One slab
 * ------------------------------------------------------------------ */

type Res = ReturnType<typeof useSharedResources>;

function Slab({
  index,
  res,
  doc,
  labelTex,
  progress,
  paused,
  frozen,
  hovered,
  setHovered,
  active,
  setActive,
}: {
  index: number;
  res: Res;
  doc?: Doc | undefined;
  labelTex?: THREE.Texture | undefined;
  progress: React.MutableRefObject<number>;
  paused: React.MutableRefObject<boolean>;
  frozen: boolean;
  hovered: number | null;
  setHovered: (i: number | null) => void;
  active: number | null;
  setActive: (i: number | null) => void;
}) {
  const group = useRef<THREE.Group>(null);
  const isHovered = hovered === index;
  const isActive = active === index;

  // double helix: two strands of SLAB_COUNT/2
  const strand = index % 2;
  const step = Math.floor(index / 2);
  const perStrand = Math.ceil(SLAB_COUNT / 2);
  const baseAngle = (step / perStrand) * Math.PI * 2 + strand * Math.PI;
  const baseY = (step / (perStrand - 1) - 0.5) * 4.6 + (strand ? 0.28 : -0.28);

  useFrame((state) => {
    const g = group.current;
    if (!g || paused.current) return;
    const t = frozen ? 0 : state.clock.elapsedTime;
    const p = frozen ? 0 : progress.current;

    // radius compresses 3.2 -> 2.0 -> 0.28 (merged monolith)
    const radius = p < 0.5 ? 3.2 - (p / 0.5) * 1.2 : 2.0 - ((p - 0.5) / 0.5) * 1.72;
    const angle = baseAngle;

    let x = Math.cos(angle) * radius;
    let z = Math.sin(angle) * radius;
    let y = baseY + Math.sin(t * 0.4 + index) * 0.08;
    let ry = -angle + Math.PI / 2;
    // as we scroll, slabs align to a single vertical column facing camera
    ry *= 1 - p;
    y *= 1 - p * 0.55;

    if (isActive) {
      x = 1.1;
      z = 3.0;
      y = 0;
      ry = 0;
    }
    if (isHovered && !isActive) z += 0.15;

    const k = 0.12;
    g.position.x += (x - g.position.x) * k;
    g.position.y += (y - g.position.y) * k;
    g.position.z += (z - g.position.z) * k;
    g.rotation.y += (ry - g.rotation.y) * k;
    const s = isActive ? 1.15 : 1;
    g.scale.setScalar(g.scale.x + (s - g.scale.x) * k);
  });

  return (
    <group
      ref={group}
      position={[Math.cos(baseAngle) * 3.2, baseY, Math.sin(baseAngle) * 3.2]}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(index);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        setHovered(null);
        document.body.style.cursor = "";
      }}
      onClick={(e) => {
        e.stopPropagation();
        setActive(isActive ? null : index);
      }}
    >
      {/* brass edge behind */}
      <mesh
        geometry={res.edgeGeo}
        material={isHovered || isActive ? res.edgeHotMat : res.edgeMat}
        position={[0, 0, -0.05]}
      />
      {/* smoked glass slab */}
      <mesh geometry={res.slabGeo} material={res.slabMat} />

      {labelTex ? (
        <mesh geometry={res.labelGeo} position={[0, 0, 0.036]}>
          <meshBasicMaterial map={labelTex} transparent depthWrite={false} />
        </mesh>
      ) : null}

      {isHovered && !isActive && doc ? (
        <Html center distanceFactor={7} position={[0, 1.35, 0.2]}>
          <div className="pointer-events-none w-52 rounded-lg border border-border bg-card/95 px-3 py-2 text-center shadow-elegant backdrop-blur">
            <p className="text-[11px] leading-snug font-semibold text-primary">
              {doc.ten}
            </p>
            <span className="mt-1.5 inline-block rounded-full border border-accent/50 bg-accent/15 px-2 py-0.5 text-[9px] font-medium text-accent-foreground">
              {doc.trangThai}
            </span>
          </div>
        </Html>
      ) : null}

      {isActive && doc ? (
        <Html center distanceFactor={6} position={[0, -1.45, 0.25]}>
          <div className="w-72 rounded-xl border border-border bg-card/97 p-3.5 text-left shadow-elegant backdrop-blur">
            <p className="font-display text-xs font-bold text-primary">{doc.ten}</p>
            <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
              {doc.soHieu}
            </p>
            <p className="mt-2 text-[11px] leading-relaxed text-foreground">
              “{doc.excerpt}”
            </p>
            <p className="mt-1.5 text-[10px] text-muted-foreground">
              — {doc.trichDan}
            </p>
            <a
              href="/tra-cuu"
              className="mt-2.5 inline-flex text-[11px] font-semibold text-accent-foreground underline decoration-dotted"
            >
              Mở trong Tra cứu →
            </a>
          </div>
        </Html>
      ) : null}
    </group>
  );
}

/* ------------------------------------------------------------------ *
 * Brass particle field
 * ------------------------------------------------------------------ */

function BrassField({
  paused,
  frozen,
}: {
  paused: React.MutableRefObject<boolean>;
  frozen: boolean;
}) {
  const ref = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const count = 800;
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 14;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 10;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 12;
    }
    return arr;
  }, []);

  useFrame((_, delta) => {
    if (!ref.current || paused.current || frozen) return;
    const dt = Math.min(delta, 0.05);
    const attr = ref.current.geometry.attributes["position"] as
      | THREE.BufferAttribute
      | undefined;
    if (!attr) return;
    const pos = attr.array as Float32Array;
    for (let i = 1; i < pos.length; i += 3) {
      const y = (pos[i] ?? 0) + dt * 0.18;
      pos[i] = y > 5 ? -5 : y;
    }
    attr.needsUpdate = true;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.012}
        color="#C8A45C"
        transparent
        opacity={0.35}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}

/* ------------------------------------------------------------------ *
 * Helix + camera
 * ------------------------------------------------------------------ */

function Helix({
  progress,
  paused,
  frozen,
  active,
  setActive,
}: {
  progress: React.MutableRefObject<number>;
  paused: React.MutableRefObject<boolean>;
  frozen: boolean;
  active: number | null;
  setActive: (i: number | null) => void;
}) {
  const res = useSharedResources();
  const spin = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState<number | null>(null);

  const labels = useMemo(
    () => DOCS.map((d) => makeLabelTexture(d.soHieu)),
    [],
  );

  useEffect(() => {
    return () => {
      labels.forEach((t) => t.dispose());
      res.slabGeo.dispose();
      res.edgeGeo.dispose();
      res.labelGeo.dispose();
      res.slabMat.dispose();
      res.edgeMat.dispose();
      res.edgeHotMat.dispose();
    };
  }, [labels, res]);

  useFrame((_, delta) => {
    if (!spin.current || paused.current || frozen) return;
    spin.current.rotation.y += Math.min(delta, 0.05) * 0.06;
  });

  return (
    <group ref={spin}>
      {Array.from({ length: SLAB_COUNT }).map((_, i) => {
        const docIndex = [1, 4, 7, 10].indexOf(i);
        return (
          <Slab
            key={i}
            index={i}
            res={res}
            doc={docIndex >= 0 ? DOCS[docIndex] : undefined}
            labelTex={docIndex >= 0 ? labels[docIndex] : undefined}
            progress={progress}
            paused={paused}
            frozen={frozen}
            hovered={hovered}
            setHovered={setHovered}
            active={active}
            setActive={setActive}
          />
        );
      })}
    </group>
  );
}

function CameraRig({
  progress,
  paused,
  frozen,
}: {
  progress: React.MutableRefObject<number>;
  paused: React.MutableRefObject<boolean>;
  frozen: boolean;
}) {
  const { camera, pointer, size } = useThree();
  const target = useMemo(() => new THREE.Vector3(), []);

  useFrame(() => {
    if (paused.current) return;
    const p = frozen ? 0 : progress.current;
    // 0% [0,0,8] · 50% [0,-1.2,5] · 100% [0,-2.5,3.5]
    const base =
      p < 0.5
        ? new THREE.Vector3(0, -(p / 0.5) * 1.2, 8 - (p / 0.5) * 3)
        : new THREE.Vector3(
            0,
            -1.2 - ((p - 0.5) / 0.5) * 1.3,
            5 - ((p - 0.5) / 0.5) * 1.5,
          );

    const wide = size.width >= 1024;
    target.set(
      base.x + (frozen ? 0 : pointer.x * 0.6) + (wide ? 1.4 : 0.9),
      base.y + (frozen ? 0 : pointer.y * 0.35),
      base.z,
    );
    camera.position.lerp(target, 0.04);
    camera.lookAt(wide ? 2.4 : 2.2, base.y * 0.45, 0);
  });

  return null;
}

/* ------------------------------------------------------------------ *
 * Scene
 * ------------------------------------------------------------------ */

export default function HeroScene() {
  const progress = useRef(0);
  const paused = useRef(false);
  const wrap = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState<number | null>(null);
  const [frozen] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  // pause when off-screen / tab hidden
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        paused.current = !entry?.isIntersecting || document.hidden;
      },
      { threshold: 0.01 },
    );
    io.observe(el);
    const onVis = () => {
      paused.current = document.hidden;
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  // scroll choreography → single ref value, no per-frame setState
  useEffect(() => {
    if (frozen || !wrap.current) return;
    const st = ScrollTrigger.create({
      trigger: wrap.current,
      start: "top top",
      end: "bottom top",
      scrub: 1,
      invalidateOnRefresh: true,
      onRefresh: (self) => {
        progress.current = self.progress;
      },
      onUpdate: (self) => {
        progress.current = self.progress;
      },
    });
    ScrollTrigger.refresh();
    return () => st.kill();
  }, [frozen]);

  const onMissClick = useCallback(() => setActive(null), []);

  return (
    <div ref={wrap} className="absolute inset-0">
      <Canvas
        dpr={[1, 1.75]}
        gl={{ antialias: true, powerPreference: "high-performance" }}
        camera={{ position: [0, 0, 8], fov: 45 }}
        onPointerMissed={onMissClick}
      >
        <ambientLight intensity={1.15} color="#FFFFFF" />
        <directionalLight position={[6, 7, 5]} intensity={2.6} color="#FFF3DC" />
        <directionalLight position={[-6, 2, -6]} intensity={1.6} color="#BFD8FF" />

        <Suspense fallback={null}>
          <Environment resolution={128} environmentIntensity={0.9}>
            <Lightformer
              intensity={2}
              color="#FFFFFF"
              position={[0, 5, -6]}
              scale={[12, 6, 1]}
            />
            <Lightformer
              intensity={1.4}
              color="#DDEBFF"
              position={[-6, 0, 4]}
              rotation-y={Math.PI / 2}
              scale={[14, 4, 1]}
            />
            <Lightformer
              intensity={1.1}
              color="#F3DCA8"
              position={[6, -2, 2]}
              rotation-y={-Math.PI / 2}
              scale={[10, 3, 1]}
            />
          </Environment>

          <PresentationControls
            global={false}
            snap
            polar={[-0.25, 0.25]}
            azimuth={[-0.5, 0.5]}
            speed={1}
          >
            <group position={[2.6, 0, 0]} scale={0.46}>
              <Helix
                progress={progress}
                paused={paused}
                frozen={frozen}
                active={active}
                setActive={setActive}
              />
            </group>
          </PresentationControls>
        </Suspense>

        <BrassField paused={paused} frozen={frozen} />
        <CameraRig progress={progress} paused={paused} frozen={frozen} />
      </Canvas>
    </div>
  );
}
