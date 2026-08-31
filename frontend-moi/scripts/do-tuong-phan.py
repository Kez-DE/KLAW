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

alias = {"background":"background","foreground":"foreground","card":"card","primary":"primary",
         "muted-foreground":"muted-foreground","accent":"accent","accent-foreground":"accent-foreground",
         "destructive":"destructive","border":"border","ring":"ring","secondary":"secondary",
         "color-paper-50":"paper-50","color-paper-100":"paper-100","color-paper-200":"paper-200",
         "color-ink-950":"ink-950","color-ink-900":"ink-900","color-brass-600":"brass-600",
         "color-brass-500":"brass-500","color-status-active":"status-active",
         "color-status-partial":"status-partial","color-status-expired":"status-expired"}

print("TOKEN                 HEX")
for k, label in alias.items():
    if k in TOK: print(f"  --{label:<20} {hexof(TOK[k])}")

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
 ("border", "background", "đường viền trên nền trang (UI 3:1)"),
 ("ring", "background", "vòng tiêu điểm trên nền trang (UI 3:1)"),
]
print("\nCẶP                                              TỈ LỆ   AA-text  AA-UI")
for fg, bg, note in pairs:
    if fg not in TOK or bg not in TOK: print("  MISSING", fg, bg); continue
    r = ratio(TOK[fg], TOK[bg])
    print(f"  {note:<46} {r:>5}:1  {'PASS' if r>=4.5 else 'FAIL':<7} {'PASS' if r>=3 else 'FAIL'}")

print("\nTÁCH ĐỘ SÁNG GIỮA CÁC MÀU TRẠNG THÁI (ảnh xám / mù màu)")
st = ["color-status-active", "color-status-partial", "color-status-expired", "muted-foreground"]
for i in range(len(st)):
    for j in range(i+1, len(st)):
        print(f"  {st[i].replace('color-','')} vs {st[j].replace('color-','')}: {ratio(TOK[st[i]], TOK[st[j]])}:1")


if __name__ == "__main__":
    # Kiểm nhỏ chạy được: khẳng định trung tâm của DESIGN.md là "còn hiệu lực" và
    # "hết hiệu lực" gần như trùng độ sáng. Nếu ai đó sửa bảng màu, dòng này gãy
    # và tài liệu phải được đo lại thay vì để trôi.
    sep = ratio(TOK["color-status-active"], TOK["color-status-expired"])
    assert sep < 1.3, f"tách độ sáng active/expired đã đổi ({sep}) — đo lại DESIGN.md"
    print(f"\nself-check OK: active vs expired vẫn {sep}:1 (< 1.3, như DESIGN.md ghi)")
