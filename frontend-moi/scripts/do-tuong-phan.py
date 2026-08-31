"""Đo tương phản WCAG 2.1 cho bảng màu KLAW.

Đọc thẳng các chuỗi oklch() trong src/styles.css nên con số trong DESIGN.md
không thể trôi khỏi mã: oklch -> Oklab -> linear sRGB -> Y -> WCAG 2.1.

Chạy:  python3 scripts/do-tuong-phan.py
"""
import math, re, pathlib, sys

def oklch_to_srgb(L, C, h_deg):
    h = math.radians(h_deg)
    a, b = C * math.cos(h), C * math.sin(h)
    l_, m_, s_ = L + 0.3963377774*a + 0.2158037573*b, L - 0.1055613458*a - 0.0638541728*b, L - 0.0894841775*a - 1.2914855480*b
    l, m, s = l_**3, m_**3, s_**3
    r = +4.0767416621*l - 3.3077115913*m + 0.2309699292*s
    g = -1.2684380046*l + 2.6097574011*m - 0.3413193965*s
    bb = -0.0041960863*l - 0.7034186147*m + 1.7076147010*s
    return (r, g, bb)                       # linear sRGB, chưa clamp

def clamp(x): return 0.0 if x < 0 else (1.0 if x > 1 else x)
def encode(c):
    c = clamp(c)
    return 12.92*c if c <= 0.0031308 else 1.055*c**(1/2.4) - 0.055
def hexof(t): return "#" + "".join(f"{round(encode(c)*255):02X}" for c in t)
def relY(t):
    r, g, b = (clamp(c) for c in t)
    return 0.2126*r + 0.7152*g + 0.0722*b
def ratio(a, b):
    ya, yb = relY(a) + 0.05, relY(b) + 0.05
    return round(max(ya, yb) / min(ya, yb), 2)

CSS = pathlib.Path(__file__).resolve().parent.parent / "src" / "styles.css"
css = CSS.read_text()
TOK = {}
for name, L, C, H in re.findall(r"--([a-z0-9-]+):\s*oklch\(([\d.]+)\s+([\d.]+)\s+([\d.]+)\)", css):
    TOK.setdefault(name, oklch_to_srgb(float(L), float(C), float(H)))

# Bí danh một tầng: `--color-status-neutral: var(--muted-foreground)`. Token
# trung tính CỐ Ý bằng màu chú thích — viết bằng var() để hai giá trị không
# thể trôi khỏi nhau, nên script phải đi theo được một tầng tham chiếu.
for name, target in re.findall(r"--([a-z0-9-]+):\s*var\(--([a-z0-9-]+)\)", css):
    if name not in TOK and target in TOK:
        TOK[name] = TOK[target]


def pha(fg, bg, ti_le=0.10):
    """Nền badge = nền trang pha `ti_le` chính màu chữ. Pha trong sRGB tuyến
    tính, cùng không gian trình duyệt hợp thành `color-mix(in oklab)` xấp xỉ —
    đủ sát để làm ngưỡng dưới, và đây là nền TỆ NHẤT chữ phải đứng lên."""
    return tuple(fg[i] * ti_le + bg[i] * (1 - ti_le) for i in range(3))

alias = {"background":"background","foreground":"foreground","card":"card","primary":"primary",
         "muted-foreground":"muted-foreground","accent":"accent","accent-foreground":"accent-foreground",
         "destructive":"destructive","border":"border","input":"input","ring":"ring",
         "secondary":"secondary",
         "color-paper-50":"paper-50","color-paper-100":"paper-100","color-paper-200":"paper-200",
         "color-ink-950":"ink-950","color-ink-900":"ink-900","color-brass-600":"brass-600",
         "color-brass-500":"brass-500","color-status-active":"status-active",
         "color-status-partial":"status-partial","color-status-expired":"status-expired",
         "color-status-neutral":"status-neutral"}

print("TOKEN                 HEX")
for k, label in alias.items():
    if k in TOK: print(f"  --{label:<20} {hexof(TOK[k])}")

# Bốn màu hiệu lực. `--color-status-neutral` là bí danh của --muted-foreground,
# nên nó có mặt ở đây với đúng vai của nó: một trong bốn màu phải tách nhau.
TRANG_THAI = [
    "color-status-active",
    "color-status-partial",
    "color-status-expired",
    "color-status-neutral",
]
NGUONG_TACH = 1.35

pairs = [
 ("foreground", "background", "chữ thân trên nền trang"),
 ("foreground", "card", "chữ thân trên thẻ"),
 ("primary", "background", "tiêu đề / chữ primary trên nền trang"),
 ("primary", "card", "tiêu đề trên thẻ"),
 ("muted-foreground", "background", "chú thích trên nền trang"),
 ("muted-foreground", "card", "chú thích trên thẻ"),
 ("muted-foreground", "color-paper-100", "chú thích trên banner paper-100"),
 ("color-brass-600", "background", "brass-600 làm CHỮ trên nền trang"),
 ("color-brass-600", "card", "brass-600 làm CHỮ trên thẻ"),
 ("color-brass-600", "color-paper-100", "brass-600 trên paper-100"),
 ("color-brass-500", "background", "brass-500 làm CHỮ trên nền trang"),
 ("accent-foreground", "accent", "chữ trên nền accent đặc"),
 ("background", "primary", "chữ trên nút primary đặc"),
 ("color-ink-950", "color-brass-500", "chữ ink trên nút brass đặc"),
 ("color-status-active", "background", "còn hiệu lực làm CHỮ trên nền trang"),
 ("color-status-active", "card", "còn hiệu lực làm CHỮ trên thẻ"),
 ("color-status-partial", "background", "một phần làm CHỮ trên nền trang"),
 ("color-status-partial", "card", "một phần làm CHỮ trên thẻ"),
 ("color-status-expired", "background", "hết hiệu lực làm CHỮ trên nền trang"),
 ("color-status-expired", "card", "hết hiệu lực làm CHỮ trên thẻ"),
 ("destructive", "background", "destructive làm CHỮ trên nền trang"),
 ("color-status-neutral", "background", "trung tính (abstain) làm CHỮ trên nền trang"),
 ("color-status-neutral", "card", "trung tính (abstain) làm CHỮ trên thẻ"),
 ("border", "background", "đường viền TRANG TRÍ trên nền trang (miễn 1.4.11)"),
 ("input", "background", "ranh giới Ô NHẬP trên nền trang (UI 3:1)"),
 ("input", "card", "ranh giới Ô NHẬP trên thẻ (UI 3:1)"),
 ("ring", "background", "vòng tiêu điểm trên nền trang (UI 3:1)"),
 ("ring", "color-paper-100", "vòng tiêu điểm trên paper-100 (UI 3:1)"),
]
print("\nCẶP                                              TỈ LỆ   AA-text  AA-UI")
for fg, bg, note in pairs:
    if fg not in TOK or bg not in TOK: print("  MISSING", fg, bg); continue
    r = ratio(TOK[fg], TOK[bg])
    print(f"  {note:<46} {r:>5}:1  {'PASS' if r>=4.5 else 'FAIL':<7} {'PASS' if r>=3 else 'FAIL'}")

# Badge hiệu lực đặt chữ lên nền pha 10% chính màu đó — nền TỆ NHẤT trong bốn
# mặt. Đo riêng, vì "4,5:1 trên --card" không nói gì về nền đã bị pha tối đi.
print("\nMÀU TRẠNG THÁI TRÊN NỀN BADGE PHA 10% (nền tệ nhất)")
NEN_XAU_NHAT = "color-paper-100"
for t in TRANG_THAI:
    r = ratio(TOK[t], pha(TOK[t], TOK[NEN_XAU_NHAT]))
    print(f"  {t.replace('color-',''):<22} {r:>5}:1  {'PASS' if r>=4.5 else 'FAIL'}")

print("\nTÁCH ĐỘ SÁNG GIỮA CÁC MÀU TRẠNG THÁI (ảnh xám / mù màu)")
for i in range(len(TRANG_THAI)):
    for j in range(i+1, len(TRANG_THAI)):
        a, b = TRANG_THAI[i], TRANG_THAI[j]
        r = ratio(TOK[a], TOK[b])
        nhan = f"  {a.replace('color-status-','')} vs {b.replace('color-status-','')}"
        print(f"{nhan:<44} {r:>5}:1  {'PASS' if r>=NGUONG_TACH else 'FAIL'}")


def kiem() -> None:
    """Kiểm chạy được cho ràng buộc KÉP của bảng màu hiệu lực.

    Trước pha 5, dòng này khẳng định điều NGƯỢC LẠI: active vs expired < 1,3
    — tức là khiếm khuyết còn đó, và tài liệu phải mô tả khiếm khuyết. Nay
    khiếm khuyết đã được sửa, nên phép kiểm đảo chiều: nó gãy nếu ai đó làm
    bảng màu tụt lại. Không có phép kiểm nào cho "không truyền đạt chỉ bằng
    màu" — đó là bất biến của thành phần, không của bảng màu.
    """
    for t in TRANG_THAI:
        for nen in ("card", "background", "color-paper-50", "color-paper-100"):
            r = ratio(TOK[t], TOK[nen])
            assert r >= 4.5, f"{t} trên {nen} chỉ {r}:1 — dưới AA 4,5"
        r = ratio(TOK[t], pha(TOK[t], TOK[NEN_XAU_NHAT]))
        assert r >= 4.5, f"{t} trên nền badge pha 10% chỉ {r}:1 — dưới AA 4,5"
    for i in range(len(TRANG_THAI)):
        for j in range(i+1, len(TRANG_THAI)):
            a, b = TRANG_THAI[i], TRANG_THAI[j]
            r = ratio(TOK[a], TOK[b])
            assert r >= NGUONG_TACH, f"{a} vs {b} chỉ tách {r}:1 — dưới {NGUONG_TACH}"
    for t, nen, nguong in (
        ("color-brass-600", "card", 4.5),
        ("color-brass-600", "color-paper-100", 4.5),
        ("ring", "background", 3.0),
        ("ring", "color-paper-100", 3.0),
        ("input", "background", 3.0),
    ):
        r = ratio(TOK[t], TOK[nen])
        assert r >= nguong, f"{t} trên {nen} chỉ {r}:1 — dưới {nguong}"
    print("\nself-check OK: 4 màu hiệu lực đều >= 4,5:1 làm chữ (kể cả trên nền")
    print(f"badge pha 10%), tách nhau >= {NGUONG_TACH}:1; brass-600, ring, input đều đạt.")


if __name__ == "__main__":
    kiem()
