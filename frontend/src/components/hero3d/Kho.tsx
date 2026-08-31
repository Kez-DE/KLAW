// oxlint-disable react/immutability -- Xem chú thích "Về quy tắc immutability" dưới đây.
import fontDiaChi from '@fontsource/jetbrains-mono/files/jetbrains-mono-latin-400-normal.woff?url';
import { Html, PresentationControls, Text } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { RefObject } from 'react';
import {
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  Group,
  MathUtils,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  type Object3D,
  PMREMGenerator,
  Points,
  PointsMaterial,
} from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { CO_NHAN, PHIEN } from './duLieuPhien';
import { docMau } from './mauTuToken';
import { TenPhien, TheTrichDoan } from './TheTrichDoan';

/**
 * Về quy tắc `immutability` bị tắt ở dòng đầu file: mọi việc trong file này là
 * sửa thuộc tính của đối tượng three.js do `useThree()` trả về —
 * `scene.environment`, `camera.position`, `material.opacity`. three.js KHÔNG có
 * API bất biến, và đưa các giá trị đó qua state nghĩa là `setState` mỗi frame,
 * đúng thứ §10.4 cấm. Quy tắc này nói về độ thuần khiết của render React; nó
 * không áp được cho `useFrame`, thứ tồn tại chính là để thoát ra khỏi React.
 * Tắt cả file, một lần, có lý do — hơn là sáu dòng `disable-next-line` rải rác.
 *
 * "Thư viện luật lơ lửng" — mười lăm phiến kính khói xếp xoắn kép quanh trục
 * dọc, mỗi phiến là MỘT VĂN BẢN CÓ THẬT (`duLieuPhien.ts`).
 *
 * Thông số hình học, vật liệu, ánh sáng và biên độ tương tác lấy nguyên văn từ
 * `KLAW-BUILD-SPEC` §10.1–10.3. Chỗ nào lệch khỏi spec đều có chú thích nêu lý
 * do ngay tại dòng đó — đừng "sửa lại cho khớp spec" mà không đọc lý do.
 *
 * BA BẤT BIẾN HIỆU NĂNG (§10.4) sống trong file này:
 *
 *   1. MỘT `BoxGeometry` cho toàn bộ 30 mesh (15 phiến + 15 viền brass) — viền
 *      dùng cùng hình, chỉ `scale` khác. BA material dùng chung, không phải một
 *      material mỗi phiến: kính · brass thường · brass đang sáng. Cái thứ ba
 *      tồn tại vì §10.2 đòi hover đổi `emissiveIntensity`, mà đổi trên material
 *      dùng chung thì cả mười lăm viền sáng cùng lúc.
 *   2. `useFrame` early-return khi `tamDungRef` bật, và MỘT vòng lặp duy nhất
 *      cập nhật cả mười lăm phiến — không phải mười lăm `useFrame`.
 *   3. Tiến trình cuộn đọc từ `tienRef`. KHÔNG `setState` mỗi frame. State chỉ
 *      đổi khi người dùng trỏ vào hoặc bấm một phiến.
 */

/** §10.1 — phiến `1.4 × 2.0 × 0.06`, xoắn kép bán kính `3.2`. */
const RONG = 1.4;
const CAO_PHIEN = 2.0;
const DAY = 0.06;
const BAN_KINH = 3.2;
/** Chiều cao cột xoắn. Không có trong spec; chọn 5.0 để 8 bậc thưa đều trong khung nhìn. */
const CAO_COT = 5.0;
const SO_HAT = 800;
/** Bán kính trong/ngoài của trường hạt: bọc quanh xoắn, không xuyên qua nó. */
const HAT_TRONG = 1.6;
const HAT_NGOAI = 5.2;
const HAT_CAO = 6;

/**
 * PRNG có hạt giống (mulberry32). Trường hạt phải GIỐNG NHAU ở mỗi lần mount:
 * `Math.random()` gọi trong thân render là không thuần khiết — StrictMode chạy
 * render hai lần và cho ra hai đám hạt khác nhau — và một cảnh không tái lập
 * được thì không so được ảnh giữa hai lần chạy.
 */
function ngauNhien(hatGiong: number): () => number {
  let hat = hatGiong;
  return () => {
    hat = (hat + 0x6d2b79f5) | 0;
    let x = Math.imul(hat ^ (hat >>> 15), 1 | hat);
    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

interface KhoProps {
  /** Tiến trình cuộn 0→1, ghi bởi KhoLuat. Đọc trong useFrame, không phải state. */
  tienRef: RefObject<number>;
  /** Ra khỏi viewport hoặc `document.hidden`. Cửa thứ hai sau `frameloop`. */
  tamDungRef: RefObject<boolean>;
  /** `prefers-reduced-motion` — đóng băng mọi chuyển động, giữ click. */
  dongBang: boolean;
  chiSoChon: number | null;
  datChiSoChon: (i: number | null) => void;
  moTraCuu: (docId: string) => void;
}

/** Vị trí gốc của từng phiến trên xoắn kép: hai nhánh lệch pha π. */
const BO_CUC = PHIEN.map((_, i) => {
  const nhanh = i % 2;
  const buoc = (i - nhanh) / 2;
  const soBuoc = Math.ceil(PHIEN.length / 2) - 1;
  return {
    goc: buoc * 0.72 + nhanh * Math.PI,
    y: (buoc / soBuoc - 0.5) * CAO_COT,
  };
});

export function Kho({
  tienRef,
  tamDungRef,
  dongBang,
  chiSoChon,
  datChiSoChon,
  moTraCuu,
}: KhoProps) {
  const { scene, gl, camera } = useThree();
  const nhomRef = useRef<Group>(null);
  const phienRefs = useRef<(Group | null)[]>([]);
  const chuRefs = useRef<(Object3D | null)[]>([]);
  const hatRef = useRef<Points>(null);
  const [chiSoHover, datChiSoHover] = useState<number | null>(null);

  /** Đồng hồ RIÊNG, tích luỹ bằng `delta`. `state.clock` vẫn chạy trong lúc
   *  cảnh bị tạm dừng, nên đọc nó là cảnh nhảy một đoạn khi cuộn trở lại. */
  const dongHoRef = useRef(0);
  const quayRef = useRef(0);

  const vatLieu = useMemo(() => {
    const hinh = new BoxGeometry(RONG, CAO_PHIEN, DAY);

    // §10.1 kính khói. `color` lấy token `--vien` (xem mauTuToken.ts để biết vì
    // sao token này chứ không phải hex của spec).
    const kinh = new MeshPhysicalMaterial({
      color: docMau('--vien'),
      transmission: 0.55,
      roughness: 0.15,
      thickness: 0.5,
      ior: 1.4,
      transparent: true,
    });

    const brass = docMau('--den-sang');
    const vien = new MeshStandardMaterial({
      color: brass,
      metalness: 0.9,
      roughness: 0.25,
      transparent: true,
    });
    const vienSang = new MeshStandardMaterial({
      color: brass,
      metalness: 0.9,
      roughness: 0.25,
      transparent: true,
      emissive: brass,
      emissiveIntensity: 0.6,
    });

    // Trường hạt brass, 800 điểm trong một vành trụ quanh xoắn.
    const hatHinh = new BufferGeometry();
    const toaDo = new Float32Array(SO_HAT * 3);
    const rnd = ngauNhien(0x4b_4c_41_57);
    for (let k = 0; k < SO_HAT; k += 1) {
      const g = rnd() * Math.PI * 2;
      const r = HAT_TRONG + rnd() * (HAT_NGOAI - HAT_TRONG);
      toaDo[k * 3] = Math.sin(g) * r;
      toaDo[k * 3 + 1] = (rnd() - 0.5) * HAT_CAO;
      toaDo[k * 3 + 2] = Math.cos(g) * r;
    }
    hatHinh.setAttribute('position', new BufferAttribute(toaDo, 3));
    const hat = new PointsMaterial({
      color: brass,
      size: 0.012,
      transparent: true,
      opacity: 0.35,
      depthWrite: false,
    });

    return { hinh, kinh, vien, vienSang, hatHinh, hat, mauChu: brass.getStyle() };
  }, []);

  useEffect(
    () => () => {
      vatLieu.hinh.dispose();
      vatLieu.kinh.dispose();
      vatLieu.vien.dispose();
      vatLieu.vienSang.dispose();
      vatLieu.hatHinh.dispose();
      vatLieu.hat.dispose();
    },
    [vatLieu],
  );

  /**
   * §10.1 đòi `<Environment preset="city" />` để brass có phản chiếu. Preset của
   * drei tải một file HDR từ CDN ngoài — thêm một request mạng vào đúng thứ
   * §10.4 đang bóp (hero tương tác được < 2,5s), và người dùng mạng yếu trả giá.
   * `RoomEnvironment` đi kèm chính gói `three`, sinh env map bằng PMREM tại chỗ:
   * cùng tác dụng (brass có gì để phản chiếu), 0 byte tải về. `intensity 0.4`
   * giữ nguyên theo spec.
   */
  useEffect(() => {
    const pmrem = new PMREMGenerator(gl);
    const phong = new RoomEnvironment();
    const mucTieu = pmrem.fromScene(phong, 0.04);
    scene.environment = mucTieu.texture;
    scene.environmentIntensity = 0.4;
    // Pass truyền sáng render lại cảnh mỗi frame; nửa phân giải là nửa số pixel
    // cho một hiệu ứng vốn đã mờ — không nhìn ra khác biệt trên kính nhám 0.15.
    gl.transmissionResolutionScale = 0.5;
    pmrem.dispose();
    phong.dispose();
    return () => {
      mucTieu.dispose();
      scene.environment = null;
    };
  }, [gl, scene]);

  useFrame((trangThai, dt) => {
    // Cửa thứ hai của §10.4. Cửa thứ nhất là `frameloop="never"` ở KhoLuat —
    // cửa đó mới thật sự tắt vòng render; cửa này chặn frame đang bay dở.
    if (tamDungRef.current) return;

    const nhom = nhomRef.current;
    if (nhom === null) return;

    const t = dongBang ? 0 : (dongHoRef.current += dt);
    const tien = dongBang ? 0 : tienRef.current;

    // §10.3 — xoắn nén dần rồi hợp thành một cột. Máy DỪNG QUAY khi một phiến
    // đang được chọn: đó là chính ẩn dụ máy đọc vi phim, khung nào đang đọc thì
    // dải phim đứng lại.
    if (!dongBang && chiSoChon === null) quayRef.current += dt * 0.06;
    nhom.rotation.y = quayRef.current;

    const banKinh =
      tien < 0.5
        ? MathUtils.lerp(BAN_KINH, 2.0, tien * 2)
        : MathUtils.lerp(2.0, 0.18, (tien - 0.5) * 2);
    const nenDoc = tien < 0.5 ? 1 : MathUtils.lerp(1, 0.18, (tien - 0.5) * 2);
    const mo = tien > 0.85 ? Math.max(0, 1 - (tien - 0.85) / 0.15) : 1;

    vatLieu.kinh.opacity = mo;
    vatLieu.vien.opacity = mo;
    vatLieu.vienSang.opacity = mo;
    vatLieu.hat.opacity = 0.35 * mo;

    // Camera: ba chặng của §10.3, cộng parallax chuột ±0.6 / ±0.35, lerp 0.04.
    const camY =
      tien < 0.5
        ? MathUtils.lerp(0, -1.2, tien * 2)
        : MathUtils.lerp(-1.2, -2.5, (tien - 0.5) * 2);
    const camZ =
      tien < 0.5 ? MathUtils.lerp(8, 5, tien * 2) : MathUtils.lerp(5, 3.5, (tien - 0.5) * 2);
    const chuot = dongBang ? { x: 0, y: 0 } : trangThai.pointer;
    camera.position.x += (chuot.x * 0.6 - camera.position.x) * 0.04;
    camera.position.y += (camY + chuot.y * 0.35 - camera.position.y) * 0.04;
    camera.position.z += (camZ - camera.position.z) * 0.04;
    camera.lookAt(0, camY * 0.5, 0);

    // Toạ độ cục bộ của "ngay trước mặt camera" khi một phiến bay ra giữa. Nhóm
    // đang quay góc q, nên world (0, y, 3) ứng với local Ry(-q)·world.
    const q = quayRef.current;

    for (let i = 0; i < BO_CUC.length; i += 1) {
      const o = phienRefs.current[i];
      if (!o) continue;
      const { goc, y } = BO_CUC[i];
      const dap = dongBang ? 0 : Math.sin(t * 0.4 + i) * 0.08;
      // Hover nâng 0.15 "về phía camera". Phiến hướng ra ngoài trục, nên nâng
      // theo pháp tuyến hướng ngoài của chính nó là xấp xỉ đúng cho các phiến
      // đang ở mặt trước — và không cần đổi hệ toạ độ mỗi frame.
      const nang = i === chiSoHover && chiSoChon === null ? 0.15 : 0;
      const r = banKinh + nang;

      let dichX = Math.sin(goc) * r;
      let dichY = y * nenDoc + dap;
      let dichZ = Math.cos(goc) * r;
      let xoay = goc;

      if (i === chiSoChon) {
        dichX = -Math.sin(q) * 3;
        dichY = camY * 0.5;
        dichZ = Math.cos(q) * 3;
        xoay = -q;
      }

      o.position.x = MathUtils.damp(o.position.x, dichX, 6, dt);
      o.position.y = MathUtils.damp(o.position.y, dichY, 6, dt);
      o.position.z = MathUtils.damp(o.position.z, dichZ, 6, dt);
      o.rotation.y = MathUtils.damp(o.rotation.y, xoay, 6, dt);

      const chu = chuRefs.current[i];
      // Nhãn WebGL có material riêng của troika, không fade cùng ba material
      // dùng chung. Cắt hẳn ở 0.88 — lúc đó cả xoắn đã mờ còn ~20% và các phiến
      // đang chồng vào một cột, bốn nhãn 0.16 đơn vị không còn đọc được nữa.
      if (chu) chu.visible = tien < 0.88;
    }

    // Hạt trôi lên. Cập nhật từng hạt (800 float) chứ không dịch cả đám: dịch cả
    // đám thì tới lúc phải quấn vòng, toàn bộ trường hạt nhảy một đoạn thấy được.
    const hat = hatRef.current;
    if (hat && !dongBang) {
      const thuoc = hat.geometry.getAttribute('position') as BufferAttribute;
      const mang = thuoc.array as Float32Array;
      for (let k = 1; k < mang.length; k += 3) {
        mang[k] += dt * 0.06;
        if (mang[k] > HAT_CAO / 2) mang[k] -= HAT_CAO;
      }
      thuoc.needsUpdate = true;
    }
  });

  const canh = (
    <group ref={nhomRef}>
      {PHIEN.map((p, i) => (
        <group
          key={p.docId + p.duongDan}
          ref={(el) => {
            phienRefs.current[i] = el;
          }}
          position={[Math.sin(BO_CUC[i].goc) * BAN_KINH, BO_CUC[i].y, Math.cos(BO_CUC[i].goc) * BAN_KINH]}
          rotation={[0, BO_CUC[i].goc, 0]}
          onPointerOver={(su) => {
            su.stopPropagation();
            datChiSoHover(i);
          }}
          onPointerOut={() => datChiSoHover(null)}
          onClick={(su) => {
            su.stopPropagation();
            datChiSoChon(chiSoChon === i ? null : i);
          }}
        >
          {/* Viền brass: CÙNG geometry, chỉ to hơn chút và lùi ra sau (§10.1). */}
          <mesh
            geometry={vatLieu.hinh}
            material={i === chiSoHover && chiSoChon === null ? vatLieu.vienSang : vatLieu.vien}
            position={[0, 0, -0.05]}
            scale={[1.07, 1.05, 0.6]}
          />
          <mesh geometry={vatLieu.hinh} material={vatLieu.kinh} />

          {CO_NHAN.has(p.soKyHieu) && (
            <Text
              ref={(el) => {
                chuRefs.current[i] = el;
              }}
              font={fontDiaChi}
              fontSize={0.16}
              color={vatLieu.mauChu}
              fillOpacity={0.55}
              anchorX="center"
              anchorY="middle"
              position={[0, 0, DAY / 2 + 0.01]}
            >
              {p.soKyHieu}
            </Text>
          )}

          {i === chiSoHover && chiSoChon === null && (
            <Html center position={[0, CAO_PHIEN / 2 + 0.35, 0.1]} zIndexRange={[20, 10]}>
              <TenPhien phien={p} />
            </Html>
          )}

          {/* Thẻ trích đoạn treo dưới CHÍNH phiến đang được chọn. Bản trước đặt
              nó trong một nhóm riêng định vị bằng `quayRef.current` đọc lúc
              render — sai hai lần: ref đọc trong render là giá trị cũ, và nhóm
              đó không được cập nhật trong useFrame nên thẻ đứng im khi phiến bay
              ra giữa. Làm con của phiến thì nó theo phiến miễn phí. */}
          {i === chiSoChon && (
            <Html center position={[0, -CAO_PHIEN / 2 - 0.5, 0.1]} zIndexRange={[40, 30]}>
              <TheTrichDoan phien={p} moTraCuu={moTraCuu} dong={() => datChiSoChon(null)} />
            </Html>
          )}
        </group>
      ))}

      <points ref={hatRef} geometry={vatLieu.hatHinh} material={vatLieu.hat} />
    </group>
  );

  return (
    <>
      {/* §10.1 — key ấm trên phải, rim lạnh sau trái, ambient 0.25. Màu lấy token. */}
      <ambientLight intensity={0.25} color={docMau('--phim')} />
      <directionalLight position={[4, 5, 3]} intensity={2.2} color={docMau('--phim')} />
      <directionalLight position={[-4, 1, -4]} intensity={1.2} color={docMau('--muc-nhat')} />

      {/* §10.2 viết `config={{ mass: 1, tension: 180 }}` — prop đó KHÔNG CÒN
          TỒN TẠI: drei 10 đã bỏ react-spring, PresentationControls giờ nhận
          `damping` (smoothTime, giây) và easing của maath. Spring cũ với mass 1
          / tension 180 / friction mặc định 26 gần tới hạn (ζ≈0.97), ổn định sau
          ~0.3s — nên `damping={0.3}` là bản dịch sát nhất, không phải một con số
          chọn bừa.

          `prefers-reduced-motion`: KHÔNG bọc PresentationControls — nó là một
          hệ dao động, tức là chuyển động. Click vẫn chạy, đúng §10.4. */}
      {dongBang ? (
        canh
      ) : (
        <PresentationControls
          polar={[-0.25, 0.25]}
          azimuth={[-0.5, 0.5]}
          snap
          damping={0.3}
        >
          {canh}
        </PresentationControls>
      )}
    </>
  );
}
