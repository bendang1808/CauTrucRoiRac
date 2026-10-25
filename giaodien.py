# -*- coding: utf-8 -*-
"""
MÔ PHỎNG HỆ THỐNG GIAO THÔNG 2x2 BLOCK (16 NGÃ TƯ) BẰNG PYGAME - dùng CODE LÕI trong core.py

CẤU TRÚC
  1 BLOCK = cụm 4 ngã tư (2x2); HỆ THỐNG = 2x2 BLOCK = A, B, C, D => 16 ngã tư (A1..D4).
            A (A1 A2 / A3 A4)  |  B (B1 B2 / B3 B4)
            -------------------+-------------------
            C (C1 C2 / C3 C4)  |  D (D1 D2 / D3 D4)
  - Mỗi ngã tư tự gọi CODE LÕI để tính chu kỳ, thời gian xanh và thời gian DỪNG (đèn đỏ)
    tối ưu theo lưu lượng riêng của nó.
  - Khu dân cư: nhà ở, cây xanh, công viên, sân thể thao và 1 SIÊU THỊ (có bãi đỗ xe) ở giữa.

ĐƯỜNG NỐI BỊ BỎ
  Cả 16 ngã tư đều có đèn. 3 đoạn đường nối giữa 2 ngã tư bị bỏ (xem DUONG_BO): A1-A2, B2-B4,
  C1-C3; hai ô phố hai bên mỗi đoạn được gộp thành một công viên lớn có hồ nước. Ngã tư mất một
  nhánh thành ngã ba: code lõi chỉ tính các dòng xe còn tồn tại nên đèn có 3 pha thay vì 4.
  Xe không bao giờ chọn đường đã bỏ; lưu lượng được ước tính theo đúng cách xe đi.

ĐIỀU KHIỂN (camera luôn bị "kẹp" trong bản đồ, không lia ra ngoài khuôn 2x2)
  Cuộn chuột / + - : zoom | kéo chuột phải/giữa hoặc W A S D : di chuyển | 0 : toàn cảnh
  Click / kéo ở góc dưới trái (vùng bản đồ nhỏ) : nhảy camera tới vị trí
  SPACE tạm dừng | M đổi chế độ Tối ưu/Cố định | G đồ thị xung đột & tô màu
  ↑ ↓ tốc độ | TAB chọn nút kế | 1-4 chọn nút trong block | R làm lại

CHẠY
  python giaodien.py              (mở cửa sổ mô phỏng)
  python giaodien.py --so-sanh    (không đồ họa, in bảng so sánh)
"""

import math
import os
import random
import sys
from functools import lru_cache

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
try:
    import pygame
except ImportError:          # vẫn chạy được --so-sanh khi chưa cài pygame
    pygame = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # import file lõi cùng thư mục
import core as loi          # <<< CODE LÕI


# ==========================================================================
# PHẦN 1. HẰNG SỐ CỦA BẢN ĐỒ (đơn vị: mét, riêng TL là số pixel / mét)
# ==========================================================================

SO_HANG, SO_COT = 4, 4                  # 4x4 ngã tư = 2x2 BLOCK (mỗi block 2x2)
KC_COT, KC_HANG = 85.0, 75.0            # khoảng cách giữa các ngã tư (m)
X0, Y0 = 40.0, 40.0                     # tọa độ ngã tư đầu tiên (m)
CX = [X0 + KC_COT * c for c in range(SO_COT)]     # hoành độ tâm các cột
CY = [Y0 + KC_HANG * r for r in range(SO_HANG)]   # tung độ tâm các hàng
RONG_M = 2 * X0 + KC_COT * (SO_COT - 1)           # bề rộng bản đồ (m)  = 335
CAO_M = 2 * Y0 + KC_HANG * (SO_HANG - 1)          # chiều cao bản đồ (m) = 305

TL = 4                                  # 1 mét = 4 pixel khi zoom = 1
ZOOM_MAX = 2.0                          # phóng to tối đa (8 pixel / mét)
RONG_BANG = 320                         # bề rộng bảng thông tin bên phải
CUA_SO_MAC_DINH = (1150, 720)

LW = 3.2                                # bề rộng 1 làn (m)
OFF = (0.5 * LW, 1.5 * LW)              # khoảng cách tim làn tới vạch giữa
NUA_DUONG = 2 * LW                      # nửa bề rộng đường (6.4 m)
VACH = NUA_DUONG + 3.2                  # vạch dừng cách tâm ngã tư (m)
XE_DAI, XE_RONG = 4.5, 2.0              # kích thước xe (m)

# Hướng chạy: 0 = sang Đông (→)  1 = xuống Nam (↓)  2 = sang Tây (←)  3 = lên Bắc (↑)
DIR = ((1, 0), (0, 1), (-1, 0), (0, -1))
LAT = tuple(DIR[(h + 1) % 4] for h in range(4))   # vector "bên phải" hướng chạy

NHAN = {0: "T", 1: "B", 2: "D", 3: "N"}           # nhãn hướng của code lõi
TEN_HUONG = loi.TEN_HUONG

# ---- Mô hình bám xe IDM ----
A_MAX, B_PHANH, T_GIAN, S0 = 1.8, 2.5, 1.2, 2.0
V_MAX, V_RE, B_VANG = 12.0, 6.0, 3.5

# ---- Xác suất hành vi của xe ----
P_PHAI = 0.12          # xe làn ngoài rẽ phải tại mỗi ngã tư
P_TRAI0 = 0.18         # xe mới vào bản đồ chọn làn rẽ trái
P_LAN_TRONG = 0.30     # sau khi rẽ, xe vào làn trong (sẽ rẽ trái ở ngã tư kế)

# ---- Lưu lượng xe vào bản đồ (xe/giờ, cả 2 làn) ----
# khóa = (hướng chạy, chỉ số hàng/cột). Vd (0, 1): xe chạy sang Đông ở hàng 1
HE_SO_LUU_LUONG = 0.72                  # chỉnh mật độ xe cả hệ thống (0.72 = giảm 20% so với 0.9)
_LUU_LUONG_CO_SO = {
    0: [600, 540, 580, 520],            # từ mép Tây vào (4 hàng)
    2: [520, 480, 500, 460],            # từ mép Đông vào (4 hàng)
    1: [440, 460, 430, 450],            # từ mép Bắc vào (4 cột)
    3: [400, 420, 410, 430],            # từ mép Nam vào (4 cột)
}
LUU_LUONG_VAO = {(h, i): q * HE_SO_LUU_LUONG
                 for h, ds in _LUU_LUONG_CO_SO.items() for i, q in enumerate(ds)}

# ---- ĐƯỜNG NỐI BỊ BỎ: cặp 2 ngã tư LIỀN KỀ (hàng, cột) mà đoạn đường giữa chúng bị bỏ ----
# (16 đường dẫn xe vào/ra mép bản đồ được giữ nguyên.)
DUONG_BO = [((0, 0), (0, 1)),            # A1 - A2
            ((0, 3), (1, 3)),            # B2 - B4
            ((2, 0), (3, 0))]            # C1 - C3
LIEN_KET_BO = {frozenset(c) for c in DUONG_BO}

# Lưu lượng bão hòa ĐO ĐƯỢC từ mô hình IDM (~2.2 s/xe thẳng, ~2.9 s/xe rẽ)
loi.LUU_LUONG_BAO_HOA = {k: (1600 if k.endswith("Th") else 1200) for k in loi.LUU_LUONG_BAO_HOA}

THOI_VANG = 3.0
CHU_KY_CO_DINH = 60
DT = 0.1

TEN_BLOCK = "ABCD"
MAU_BLOCK = [(255, 200, 90), (110, 205, 255), (140, 235, 150), (245, 150, 210)]


def chi_so_block(r, c):
    """Ngã tư (r, c) thuộc block nào: 0=A (trên-trái) 1=B (trên-phải) 2=C 3=D."""
    return (r // 2) * 2 + (c // 2)


# ==========================================================================
# PHẦN 2. HÀM HÌNH HỌC TRÊN LƯỚI
# ==========================================================================

def lang_gieng(r, c, h):
    """Ngã tư kế tiếp theo hướng h (None nếu ra ngoài lưới)."""
    dc, dr = DIR[h]
    r2, c2 = r + dr, c + dc
    return (r2, c2) if 0 <= r2 < SO_HANG and 0 <= c2 < SO_COT else None


def s_tam(h, r, c):
    """'Tọa độ dọc đường' (s) của tâm ngã tư (r, c) khi chạy theo hướng h."""
    return CX[c] * DIR[h][0] + CY[r] * DIR[h][1]


def thong_tin_cua_vao(h, idx):
    """Cửa vào bản đồ: (chỉ số đường, s lúc sinh xe, ngã tư đầu tiên)."""
    return {0: (idx, -3.0, (idx, 0)),
            2: (idx, -(RONG_M + 3.0), (idx, SO_COT - 1)),
            1: (idx, -3.0, (0, idx)),
            3: (idx, -(CAO_M + 3.0), (SO_HANG - 1, idx))}[h]


S_RA = {0: RONG_M + 3.0, 1: CAO_M + 3.0, 2: 3.0, 3: 3.0}
HUONG_TU_NHAN = {v: k for k, v in NHAN.items()}


def co_duong(r, c, h):
    """Từ ngã tư (r, c) có đường đi theo hướng h không? (False nếu đoạn đó đã bị bỏ)."""
    n = lang_gieng(r, c, h)
    return n is None or frozenset(((r, c), n)) not in LIEN_KET_BO


def lan_hop_le(nut, h, lan):
    """Làn `lan` (0 = trong/rẽ trái, 1 = ngoài/thẳng-phải) tới ngã tư `nut` theo hướng h có
    ít nhất một lối ra không? (nut = None: sắp ra khỏi bản đồ)"""
    if nut is None:
        return True
    r, c = nut
    if lan == 0:
        return co_duong(r, c, (h + 3) % 4)
    return co_duong(r, c, h) or co_duong(r, c, (h + 1) % 4)


def _chon_lan(nut, h, ds):
    """Giữ các (làn, xác suất) có lối ra ở ngã tư `nut`, rồi chuẩn hóa xác suất về tổng 1."""
    ds = [(l, p) for l, p in ds if lan_hop_le(nut, h, l)]
    tong = sum(p for _, p in ds)
    return [(l, p / tong) for l, p in ds]


@lru_cache(maxsize=None)
def phan_phoi_chuyen_dong(r, c, h, lan):
    """
    Xe đang tới ngã tư (r, c) theo hướng h ở làn `lan` sẽ đi thế nào? Trả về danh sách
    (kiểu, hướng mới, làn mới, xác suất); kiểu: T thẳng, R phải, L trái. Chỉ chọn lối còn
    đường và dẫn tới làn hợp lệ ở ngã tư kế (tránh đường cụt). Dùng chung cho mô phỏng và
    ước tính lưu lượng nên hai bên luôn khớp nhau.
    """
    ung_vien = ([("L", (h + 3) % 4, 1.0)] if lan == 0 else
                [("T", h, 1 - P_PHAI), ("R", (h + 1) % 4, P_PHAI)])
    hop = []                                          # (kiểu, hướng, trọng số, [(làn, xác suất)])
    for cd, h2, w in ung_vien:
        if not co_duong(r, c, h2):
            continue
        n2 = lang_gieng(r, c, h2)
        if cd == "T":                                 # đi thẳng thì giữ nguyên làn
            ds = [(lan, 1.0)] if lan_hop_le(n2, h2, lan) else []
        else:                                         # rẽ thì chọn làn trong/ngoài ở đường mới
            ds = _chon_lan(n2, h2, ((0, P_LAN_TRONG), (1, 1 - P_LAN_TRONG)))
        if ds:
            hop.append((cd, h2, w, ds))
    tong_w = sum(x[2] for x in hop)
    return [(cd, h2, l2, w / tong_w * p) for cd, h2, w, ds in hop for l2, p in ds]


def phan_phoi_lan_vao(nut, h):
    """Xe mới vào bản đồ chọn làn nào (chỉ chọn làn có lối ra ở ngã tư đầu tiên)."""
    return _chon_lan(nut, h, ((0, P_TRAI0), (1, 1 - P_TRAI0)))


def dong_xe_ton_tai(r, c):
    """Các dòng xe (nhãn code lõi) thực sự có ở ngã tư (r, c) khi một số đường đã bị bỏ."""
    ds = []
    for h in range(4):
        if not co_duong(r, c, (h + 2) % 4):          # nhánh mà xe hướng h đi tới đã bị bỏ
            continue
        if co_duong(r, c, h):
            ds.append(NHAN[h] + "_Th")
        if co_duong(r, c, (h + 3) % 4):
            ds.append(NHAN[h] + "_Re")
    return ds


def _luong_vao_bien():
    """Các (trạng thái xe, lưu lượng) sinh ra ở mép bản đồ; trạng thái = (hàng, cột, hướng, làn)."""
    for (h, idx), q in LUU_LUONG_VAO.items():
        _, _, nut = thong_tin_cua_vao(h, idx)
        for lan, p in phan_phoi_lan_vao(nut, h):
            yield (nut[0], nut[1], h, lan), q * p


def kiem_tra_mang():
    """Kiểm tra mạng đường sau khi bỏ đoạn nối: không trạng thái xe nào hết lối đi và từ mọi
    trạng thái đều còn đường ra khỏi bản đồ. Trả về danh sách lỗi (rỗng = tốt)."""
    loi_, trang_thai, hang_doi, canh = [], set(), [st for st, _ in _luong_vao_bien()], {}
    while hang_doi:
        st = hang_doi.pop()
        if st in trang_thai:
            continue
        trang_thai.add(st)
        r, c, h, lan = st
        ds = phan_phoi_chuyen_dong(r, c, h, lan)
        if not ds:
            loi_.append(f"Xe hết lối đi tại ngã tư ({r},{c}) hướng {h} làn {lan}")
        canh[st] = []
        for cd, h2, l2, p in ds:
            n = lang_gieng(r, c, h2)
            if n is None:
                canh[st].append(None)                 # ra khỏi bản đồ
            else:
                canh[st].append((n[0], n[1], h2, l2))
                hang_doi.append((n[0], n[1], h2, l2))
    thoat = {st for st, ks in canh.items() if None in ks}   # lan ngược từ các trạng thái thoát được
    doi = True
    while doi:
        doi = False
        for st, ks in canh.items():
            if st not in thoat and any(k in thoat for k in ks if k is not None):
                thoat.add(st)
                doi = True
    return loi_ + [f"Xe có thể bị kẹt vòng quanh, không ra được: {st}" for st in trang_thai - thoat]


# ==========================================================================
# PHẦN 3. ƯỚC TÍNH LƯU LƯỢNG TỪNG HƯỚNG CỦA TỪNG NGÃ TƯ
# ==========================================================================

def tinh_luu_luong_cac_nut():
    """
    Lan truyền dòng xe từ mép bản đồ qua mạng lưới (lặp đến khi ổn định) để ước tính lưu
    lượng từng hướng của từng ngã tư theo định dạng code lõi ("B_Th", "B_Re", ...). Dùng đúng
    mô hình định tuyến của mô phỏng nên đã tính đến những đoạn đường bị bỏ.
    """
    tu_ngoai = {}
    for k, f in _luong_vao_bien():
        tu_ngoai[k] = tu_ngoai.get(k, 0.0) + f

    vao = dict(tu_ngoai)
    for _ in range(120):
        moi = dict(tu_ngoai)
        for (r, c, h, lan), f in vao.items():
            for cd, h2, l2, p in phan_phoi_chuyen_dong(r, c, h, lan):
                n = lang_gieng(r, c, h2)
                if n is not None:
                    k = (n[0], n[1], h2, l2)
                    moi[k] = moi.get(k, 0.0) + f * p
        vao = moi

    ket_qua = {}
    for r in range(SO_HANG):
        for c in range(SO_COT):
            fl = {}
            for khoa in dong_xe_ton_tai(r, c):
                h = HUONG_TU_NHAN[khoa[0]]
                if khoa.endswith("Th"):      # xe rẽ phải đi tự do nên KHÔNG tính vào dòng đi thẳng
                    f = vao.get((r, c, h, 1), 0) * sum(
                        p for cd, _, _, p in phan_phoi_chuyen_dong(r, c, h, 1) if cd == "T")
                else:
                    f = vao.get((r, c, h, 0), 0)
                fl[khoa] = max(5, round(f))
            ket_qua[(r, c)] = fl
    return ket_qua


# ==========================================================================
# PHẦN 4. KẾ HOẠCH ĐÈN (GỌI CODE LÕI)
# ==========================================================================

class KeHoach:
    """Kế hoạch đèn của một ngã tư: mỗi pha = [XANH g giây][VÀNG 3 giây][ĐỎ TOÀN PHẦN]."""

    def __init__(self, ten, cac_pha, xanh, chu_ky, mat, qua_tai=False):
        self.ten, self.cac_pha, self.xanh = ten, cac_pha, xanh
        self.chu_ky, self.mat, self.qua_tai = chu_ky, mat, qua_tai
        self.bat_dau, self.moc, a = [], {}, 0.0
        for pha, g in zip(cac_pha, xanh):
            self.bat_dau.append(a)
            for dong_xe in pha:
                self.moc[dong_xe] = (a, a + g, a + g + THOI_VANG)   # (bắt đầu, hết xanh, hết vàng)
            a += g + mat
        self.dung = [chu_ky - g - mat for g in xanh]      # thời gian DỪNG (đèn đỏ) của từng pha

    def trang_thai(self, dong_xe, u):
        a, het_xanh, het_vang = self.moc[dong_xe]
        return "G" if a <= u < het_xanh else "Y" if het_xanh <= u < het_vang else "R"

    def con_lai(self, dong_xe, u):
        a, het_xanh, het_vang = self.moc[dong_xe]
        if a <= u < het_xanh:
            return het_xanh - u
        if het_xanh <= u < het_vang:
            return het_vang - u
        return (a - u) % self.chu_ky

    def pha_hien_tai(self, u):
        return max((i for i, b in enumerate(self.bat_dau) if u >= b), default=0)


def tao_ke_hoach_toi_uu(luu_luong):
    """>>> GỌI CODE LÕI <<<  đồ thị xung đột -> tô màu -> pha -> Webster -> chia xanh."""
    loi.LUU_LUONG = dict(luu_luong)
    tat_ca = loi.CAC_DONG_XE
    loi.CAC_DONG_XE = [k for k in tat_ca if k in luu_luong]   # ngã ba: chỉ các dòng xe thật sự có
    try:
        do_thi = loi.tao_do_thi_xung_dot()
        cac_pha, _ = loi.chon_cach_chia_pha_tot_nhat(do_thi)
    finally:
        loi.CAC_DONG_XE = tat_ca
    cac_pha.sort(key=lambda p: (0 if p[0][0] in "BN" else 1, 0 if p[0].endswith("Th") else 1))

    y_pha = loi.tinh_y_toi_han_moi_pha(cac_pha)
    mat = loi.THOI_GIAN_MAT_MOI_PHA
    L = mat * len(cac_pha)
    C0 = loi.chu_ky_webster(L, sum(y_pha))
    qua_tai = C0 is None
    C = loi.CHU_KY_MAX if qua_tai else int(round(min(max(C0, loi.CHU_KY_MIN), loi.CHU_KY_MAX)))
    C = max(C, L + loi.XANH_TOI_THIEU * len(cac_pha))
    kh = KeHoach("Tối ưu (Webster)", cac_pha, loi.chia_thoi_gian_xanh(y_pha, C, L), C, mat, qua_tai)
    kh.do_thi = do_thi                       # để cửa sổ đồ thị vẽ đúng đồ thị của ngã tư này
    return kh


def tao_ke_hoach_co_dinh(cac_pha):
    """Phương án so sánh: chu kỳ cố định 60 giây, chia đều thời gian xanh."""
    mat, n = loi.THOI_GIAN_MAT_MOI_PHA, len(cac_pha)
    g = (CHU_KY_CO_DINH - mat * n) // n
    return KeHoach("Cố định 60s", cac_pha, [g] * n, g * n + mat * n, mat)


class NutGiaoThong:
    """Một ngã tư: tên (A1..D4), lưu lượng, 2 kế hoạch đèn (tối ưu / cố định)."""

    def __init__(self, stt, r, c, luu_luong):
        self.stt, self.r, self.c = stt, r, c
        self.block = chi_so_block(r, c)
        self.ten = f"{TEN_BLOCK[self.block]}{(r % 2) * 2 + (c % 2) + 1}"
        self.luu_luong = luu_luong
        self.cx, self.cy = CX[c], CY[r]
        toi_uu = tao_ke_hoach_toi_uu(luu_luong)
        co_dinh = tao_ke_hoach_co_dinh(toi_uu.cac_pha)
        co_dinh.do_thi = toi_uu.do_thi
        self.kh = {"toi_uu": toi_uu, "co_dinh": co_dinh}
        self.che_do = "toi_uu"
        self.lech = (stt * 11) % toi_uu.chu_ky      # lệch pha giữa các ngã tư

    @property
    def ke_hoach(self):
        return self.kh[self.che_do]

    def u(self, t):
        """Thời điểm t quy về vị trí trong chu kỳ."""
        return (t + self.lech) % self.ke_hoach.chu_ky

    def trang_thai(self, dong_xe, t):
        return self.ke_hoach.trang_thai(dong_xe, self.u(t))


# ==========================================================================
# PHẦN 5. XE VÀ MÔ HÌNH MÔ PHỎNG
# ==========================================================================

class Xe:
    """Một chiếc xe. s = vị trí ĐẦU xe dọc theo đường (m). cd = kiểu đi (T/R/L), lane_dich =
    làn sau khi rẽ (cả hai do MoPhong._chon_chuyen_dong gán ngay khi sinh xe / qua ngã tư)."""
    __slots__ = ("h", "road", "lane", "s", "v", "a", "v0", "nut", "cd",
                 "lane_dich", "da_qua_vach", "goc", "mau", "t_sinh", "t_dung")

    def __init__(self, h, road, lane, s, v0, nut, mau, t_sinh):
        self.h, self.road, self.lane, self.s = h, road, lane, s
        self.v0, self.v, self.a = v0, min(8.0, v0), 0.0
        self.nut, self.da_qua_vach, self.goc = nut, False, h * 90.0
        self.mau, self.t_sinh, self.t_dung = mau, t_sinh, 0.0

    def vi_tri_tai(self, s):
        h = self.h
        if h in (0, 2):
            return s * DIR[h][0], CY[self.road] + OFF[self.lane] * LAT[h][1]
        return CX[self.road] + OFF[self.lane] * LAT[h][0], s * DIR[h][1]

    def vi_tri(self):
        return self.vi_tri_tai(self.s)


def idm(v, v0, khoang_cach, dv):
    """Mô hình bám xe IDM."""
    s_mong_muon = S0 + max(0.0, v * T_GIAN + v * dv / (2 * math.sqrt(A_MAX * B_PHANH)))
    return A_MAX * (1 - (v / v0) ** 4 - (s_mong_muon / max(khoang_cach, 0.1)) ** 2)


MAU_XE = [(235, 235, 240), (90, 160, 240), (240, 190, 60), (200, 80, 80),
          (110, 200, 140), (170, 120, 220), (240, 140, 70), (150, 160, 170)]


class MoPhong:
    """Toàn bộ thế giới mô phỏng (không phụ thuộc pygame)."""

    def __init__(self, seed=1, he_so_xe=1.0):
        self.rng = random.Random(seed)
        self.he_so_xe = he_so_xe
        self.t = 0.0
        self.xe = []
        self.hang_cho = {k: [] for k in LUU_LUONG_VAO}
        loi_mang = kiem_tra_mang()
        if loi_mang:
            raise ValueError("Mạng đường sau khi bỏ đoạn nối có lỗi: " + "; ".join(loi_mang[:3]))
        luu_luong = tinh_luu_luong_cac_nut()
        self.nut = [[NutGiaoThong(r * SO_COT + c + 1, r, c, luu_luong[(r, c)]) for c in range(SO_COT)]
                    for r in range(SO_HANG)]
        self.ds_nut = [n for hang in self.nut for n in hang]
        self.che_do = "toi_uu"
        self.xoa_thong_ke()

    def dat_che_do(self, che_do):
        self.che_do = che_do
        for n in self.ds_nut:
            n.che_do = che_do

    def xoa_thong_ke(self):
        self.tk = {k: {"n": 0, "dung": 0.0, "hanh_trinh": 0.0} for k in ("toi_uu", "co_dinh")}

    def chay(self, giay):
        for _ in range(int(giay / DT)):
            self.buoc(DT)

    def _boc_tham(self, ds):
        """Chọn ngẫu nhiên một giá trị từ danh sách [(giá trị, xác suất)] (tổng xác suất = 1)."""
        x, acc = self.rng.random(), 0.0
        for gia_tri, p in ds:
            acc += p
            if x <= acc:
                break
        return gia_tri

    def _chon_chuyen_dong(self, xe):
        """Quyết định xe sẽ đi thế nào ở ngã tư sắp tới (lấy mẫu từ phan_phoi_chuyen_dong):
        làn trong -> rẽ trái; làn ngoài -> thẳng hoặc rẽ phải; không chọn đường đã bị bỏ."""
        ds = phan_phoi_chuyen_dong(*xe.nut, xe.h, xe.lane) if xe.nut is not None else None
        if not ds:                                   # sắp ra khỏi bản đồ (hoặc không xảy ra: có kiem_tra_mang)
            xe.cd, xe.lane_dich = "T", xe.lane
            return
        xe.cd, xe.lane_dich = self._boc_tham([((cd, l2), p) for cd, _, l2, p in ds])

    def _sinh_xe(self, dt, lanes):
        for (h, idx), q in LUU_LUONG_VAO.items():
            hang = self.hang_cho[(h, idx)]
            road, s0, nut = thong_tin_cua_vao(h, idx)
            if self.rng.random() < q * self.he_so_xe * dt / 3600.0 and len(hang) < 40:
                hang.append(self._boc_tham(phan_phoi_lan_vao(nut, h)))
            con_cho = []
            for lan in hang:
                lst = lanes.get((h, road, lan))
                if lst and min(x.s for x in lst) - XE_DAI - s0 <= 9.0:    # chưa đủ chỗ trống
                    con_cho.append(lan)
                    continue
                v0 = V_MAX * self.rng.uniform(0.85, 1.1)
                xe = Xe(h, road, lan, s0, v0, nut, self.rng.choice(MAU_XE), self.t)
                self._chon_chuyen_dong(xe)
                self.xe.append(xe)
                lanes.setdefault((h, road, lan), []).append(xe)
            self.hang_cho[(h, idx)] = con_cho

    def _tinh_gia_toc(self, xe, truoc):
        """Gia tốc của xe theo IDM; `truoc` là xe đi ngay trước cùng làn (hoặc None). Vạch dừng
        khi đèn đỏ / vàng đủ xa để phanh được coi như một "xe đứng yên" chắn đường."""
        khoang, v_truoc = (truoc.s - XE_DAI - xe.s, truoc.v) if truoc is not None else (1e9, 0.0)
        v0 = xe.v0
        if xe.nut is not None:
            r, c = xe.nut
            sc = s_tam(xe.h, r, c)
            if xe.cd != "T" and sc - xe.s < 25:
                v0 = min(v0, V_RE)                   # chậm lại trước khi rẽ
            if not xe.da_qua_vach:
                d = sc - VACH - xe.s                 # khoảng cách tới vạch dừng
                if d < 0.3:
                    xe.da_qua_vach = True
                elif xe.cd != "R":                   # rẽ phải đi tự do, không xét đèn
                    den = self.nut[r][c].trang_thai(NHAN[xe.h] + ("_Th" if xe.cd == "T" else "_Re"), self.t)
                    if den == "Y" and xe.v * xe.v / (2 * d) > B_VANG:
                        xe.da_qua_vach = True        # vàng mà không kịp phanh -> đi luôn
                    elif den != "G" and d < khoang:
                        khoang, v_truoc = d, 0.0
        xe.a = max(-9.0, idm(xe.v, v0, khoang, xe.v - v_truoc))

    def buoc(self, dt):
        self.t += dt
        lanes = {}
        for xe in self.xe:
            lanes.setdefault((xe.h, xe.road, xe.lane), []).append(xe)
        self._sinh_xe(dt, lanes)

        for lst in lanes.values():
            lst.sort(key=lambda x: x.s)
            for i, xe in enumerate(lst):
                self._tinh_gia_toc(xe, lst[i + 1] if i + 1 < len(lst) else None)

        con_lai, tk = [], self.tk[self.che_do]
        for xe in self.xe:
            xe.v = max(0.0, xe.v + xe.a * dt)
            xe.s += xe.v * dt
            if xe.v < 0.3:
                xe.t_dung += dt
            lech = ((xe.h * 90.0 - xe.goc + 180.0) % 360.0) - 180.0      # xoay dần về hướng chạy
            buoc_xoay = 300.0 * dt
            xe.goc = (xe.goc + max(-buoc_xoay, min(buoc_xoay, lech))) % 360.0
            if xe.nut is not None:
                self._xu_ly_nut(xe)
            if xe.s > S_RA[xe.h]:                    # ra khỏi bản đồ: ghi thống kê
                tk["n"] += 1
                tk["dung"] += xe.t_dung
                tk["hanh_trinh"] += self.t - xe.t_sinh
            else:
                con_lai.append(xe)
        self.xe = con_lai

    def _xu_ly_nut(self, xe):
        r, c = xe.nut
        sc = s_tam(xe.h, r, c)
        if xe.cd == "T":
            if xe.s >= sc:
                xe.nut = lang_gieng(r, c, xe.h)
                xe.da_qua_vach = False
                self._chon_chuyen_dong(xe)
            return
        h2 = (xe.h + 3) % 4 if xe.cd == "L" else (xe.h + 1) % 4
        s_re = sc + OFF[xe.lane_dich] * (LAT[h2][0] * DIR[xe.h][0] + LAT[h2][1] * DIR[xe.h][1])
        if xe.s >= s_re:                             # tới điểm rẽ: chuyển sang đường mới
            x, y = xe.vi_tri_tai(s_re)
            xe.s = x * DIR[h2][0] + y * DIR[h2][1]
            xe.road = c if xe.h in (0, 2) else r
            xe.h, xe.lane = h2, xe.lane_dich
            xe.nut = lang_gieng(r, c, h2)
            xe.da_qua_vach = False
            self._chon_chuyen_dong(xe)

    def thong_ke(self, che_do=None):
        """(số xe đã qua, thời gian dừng TB, hành trình TB)."""
        d = self.tk[che_do or self.che_do]
        if d["n"] == 0:
            return 0, 0.0, 0.0
        return d["n"], d["dung"] / d["n"], d["hanh_trinh"] / d["n"]


def so_sanh_khong_do_hoa(khoi_dong=300, do_dai=1500, seed=3):
    """Chạy cùng một kịch bản với 2 chế độ đèn rồi in bảng so sánh."""
    print(f"Chạy so sánh: khởi động {khoi_dong}s, đo {do_dai}s mô phỏng ...")
    ket_qua = {}
    for che in ("toi_uu", "co_dinh"):
        mp = MoPhong(seed=seed)
        mp.dat_che_do(che)
        mp.chay(khoi_dong)
        mp.xoa_thong_ke()
        mp.chay(do_dai)
        dung_xe = sum(1 for x in mp.xe if x.v < 0.3)
        ket_qua[che] = mp.thong_ke() + (len(mp.xe), dung_xe)
    print(f"{'Chế độ':<18}{'Xe đã qua':>10}{'Dừng TB (s)':>13}{'Hành trình TB (s)':>19}{'Xe tồn':>8}")
    for che, ten in (("toi_uu", "Tối ưu Webster"), ("co_dinh", "Cố định 60s")):
        n, dung, ht, ton, _ = ket_qua[che]
        print(f"{ten:<18}{n:>10}{dung:>13.1f}{ht:>19.1f}{ton:>8}")
    return ket_qua


# ==========================================================================
# PHẦN 6. CAMERA - BỊ KẸP TRONG KHUÔN BẢN ĐỒ 2x2
# ==========================================================================

class Camera:
    """
    Camera 2D: zoom + pan, LUÔN nằm trong bản đồ.  Công thức: pixel = mét * (TL * zoom) + pan
    Quy tắc kẹp (hàm kep):
      1. zoom >= zoom_min (mức vừa đủ để bản đồ phủ kín khung nhìn) => không thấy phần ngoài bản đồ.
      2. pan_x trong [vw - rộng_bản_đồ, 0], pan_y tương tự => kéo đến mép bản đồ là dừng.
    """

    def __init__(self, vw, vh):
        self.vw, self.vh = vw, vh
        self.zoom, self.px, self.py = 1.0, 0.0, 0.0
        self.dat_lai()

    @property
    def k(self):
        """Số pixel trên 1 mét hiện tại."""
        return TL * self.zoom

    def zoom_min(self):
        return max(self.vw / (RONG_M * TL), self.vh / (CAO_M * TL))

    def kep(self):
        """Ép zoom và pan vào giới hạn cho phép."""
        self.zoom = max(self.zoom_min(), min(ZOOM_MAX, self.zoom))
        k = self.k
        self.px = float(round(min(0.0, max(self.vw - RONG_M * k, self.px))))
        self.py = float(round(min(0.0, max(self.vh - CAO_M * k, self.py))))

    def dat_kich_thuoc(self, vw, vh):
        """Gọi khi cửa sổ đổi kích thước (giữ nguyên điểm giữa khung nhìn)."""
        if (vw, vh) != (self.vw, self.vh):
            tam = self.tam_the_gioi()
            self.vw, self.vh = vw, vh
            self.tam_o(*tam)

    def dat_lai(self):
        """Về toàn cảnh: thu nhỏ hết cỡ, căn giữa bản đồ."""
        self.zoom = self.zoom_min()
        self.tam_o(RONG_M / 2, CAO_M / 2)

    def tam_the_gioi(self):
        """Tọa độ (mét) của điểm giữa khung nhìn."""
        return (self.vw / 2 - self.px) / self.k, (self.vh / 2 - self.py) / self.k

    def tam_o(self, wx, wy):
        """Đặt điểm giữa khung nhìn tại (wx, wy) mét."""
        self.px = self.vw / 2 - wx * self.k
        self.py = self.vh / 2 - wy * self.k
        self.kep()

    def zoom_tai(self, mx, my, he_so):
        """Zoom hướng tâm về con trỏ chuột (mx, my)."""
        z_cu = self.zoom
        z_moi = max(self.zoom_min(), min(ZOOM_MAX, z_cu * he_so))
        self.px = mx - (mx - self.px) * (z_moi / z_cu)
        self.py = my - (my - self.py) * (z_moi / z_cu)
        self.zoom = z_moi
        self.kep()

    def keo(self, dx, dy):
        self.px += dx
        self.py += dy
        self.kep()

    def sang_man_hinh(self, x, y):
        return x * self.k + self.px, y * self.k + self.py

    def sang_the_gioi(self, sx, sy):
        return (sx - self.px) / self.k, (sy - self.py) / self.k


# ==========================================================================
# PHẦN 7. TRANG TRÍ BẢN ĐỒ: NHÀ, CÂY, CÔNG VIÊN, SIÊU THỊ (vẽ 1 lần)
# ==========================================================================
# Toàn bộ phần tĩnh được vẽ MỘT LẦN vào một ảnh lớn ở nhiều độ phân giải, sau đó chỉ cắt +
# thu phóng khi vẽ. Mọi hàm ở đây vẽ theo MÉT; S = số pixel trên mét của ảnh đang vẽ.

MAU_CO = (44, 70, 52)
MAU_DAT_THO = (74, 122, 80)          # nền lô đất (cỏ)
MAU_VIA_HE = (150, 152, 160)
MAU_DUONG = (58, 60, 68)
MAU_DEN = {"G": (70, 225, 100), "Y": (255, 205, 50), "R": (240, 65, 65)}
MAU_PHA = [(80, 160, 255), (255, 150, 60), (120, 220, 120), (220, 110, 220)]
MAU_MAI = [(184, 78, 64), (196, 108, 70), (120, 132, 152), (150, 100, 82),
           (92, 122, 142), (170, 62, 62), (205, 160, 84), (112, 142, 112)]
MAU_TUONG = [(238, 230, 216), (230, 226, 210), (244, 238, 226), (222, 218, 205)]


def _rect(S, x0, y0, x1, y1):
    """Hình chữ nhật từ tọa độ mét (làm tròn 2 đầu để không hở khe)."""
    a, b = round(x0 * S), round(y0 * S)
    return pygame.Rect(a, b, max(1, round(x1 * S) - a), max(1, round(y1 * S) - b))


def _to(nen, S, mau, *toa_do):
    """Tô hình chữ nhật (x0, y0, x1, y1 tính bằng mét)."""
    nen.fill(mau, _rect(S, *toa_do))


def _px(S, x, y):
    """Điểm (mét) -> pixel."""
    return round(x * S), round(y * S)


def _net(nen, S, mau, a, b, rong):
    """Đoạn thẳng từ a đến b (mét), bề rộng `rong` mét."""
    pygame.draw.line(nen, mau, _px(S, *a), _px(S, *b), max(1, round(rong * S)))


def _toi(mau, f):
    return tuple(max(0, min(255, int(v * f))) for v in mau)


def ve_cay(nen, S, x, y, r):
    """Cây nhìn từ trên xuống: bóng + tán lá + điểm sáng."""
    pygame.draw.circle(nen, (50, 92, 58), _px(S, x + 0.5, y + 0.6), max(1, round(r * S)))
    pygame.draw.circle(nen, (46, 114, 60), _px(S, x, y), max(1, round(r * S)))
    pygame.draw.circle(nen, (78, 152, 86), _px(S, x - 0.25 * r, y - 0.3 * r), max(1, round(r * 0.58 * S)))


def ve_nha(nen, S, x, y, w, d, mai, mat_truoc):
    """Ngôi nhà nhìn từ trên xuống (x, y = góc trên-trái, w x d mét).
    mat_truoc: 'B' = mặt tiền quay lên phía Bắc (cạnh y nhỏ), 'N' = quay xuống phía Nam."""
    _to(nen, S, _toi(MAU_DAT_THO, 0.78), x + 0.9, y + 0.9, x + w + 0.9, y + d + 0.9)   # bóng đổ
    _to(nen, S, MAU_TUONG[int(x * 7 + y * 3) % len(MAU_TUONG)], x, y, x + w, y + d)    # tường
    xi0, xi1, yi0, yi1 = x + 0.4, x + w - 0.4, y + 0.4, y + d - 0.4
    ym, xm = (yi0 + yi1) / 2, x + w / 2
    sang, toi = mai, _toi(mai, 0.8)                  # nửa mái phía mặt tiền sáng hơn
    if mat_truoc == "B":
        _to(nen, S, sang, xi0, yi0, xi1, ym)
        _to(nen, S, toi, xi0, ym, xi1, yi1)
        cua, loi_di = (xm - 0.6, y - 0.05, xm + 0.6, y + 0.55), (xm - 0.6, y - 1.0, xm + 0.6, y)
        ong_khoi = (xi1 - 2.0, yi1 - 2.0, xi1 - 1.0, yi1 - 1.0)
    else:
        _to(nen, S, toi, xi0, yi0, xi1, ym)
        _to(nen, S, sang, xi0, ym, xi1, yi1)
        cua, loi_di = (xm - 0.6, y + d - 0.55, xm + 0.6, y + d + 0.05), (xm - 0.6, y + d, xm + 0.6, y + d + 1.0)
        ong_khoi = (xi1 - 2.0, yi0 + 1.0, xi1 - 1.0, yi0 + 2.0)
    _to(nen, S, (196, 196, 202), *loi_di)                          # lối đi vào nhà
    _net(nen, S, _toi(mai, 1.3), (xi0, ym), (xi1, ym), 0.28)       # nóc mái
    _to(nen, S, (78, 66, 62), *ong_khoi)                           # ống khói / máy lạnh
    _to(nen, S, (110, 78, 54), *cua)                               # cửa chính


def ve_hang_nha(nen, S, rng, x0, x1, y, d, mat_truoc, ds_cay):
    """Một hàng nhà dọc theo cạnh trên/dưới của lô đất."""
    x = x0 + 1.0
    while True:
        w = rng.uniform(7.5, 10.5)
        if x + w > x1 - 1.0:
            break
        ve_nha(nen, S, x, y, w, d, rng.choice(MAU_MAI), mat_truoc)
        if rng.random() < 0.55:                    # cây nhỏ bên cạnh nhà
            cy = y - 1.6 if mat_truoc == "B" else y + d + 1.6
            ds_cay.append((x + w + 0.9, cy, rng.uniform(0.9, 1.3)))
        x += w + rng.uniform(1.8, 3.2)


def ve_vung_giua(nen, S, rng, x0, y0, x1, y1, ds_cay, lon=False):
    """Khoảng sân giữa 2 hàng nhà: công viên / sân thể thao / vườn rau / vườn cây."""
    w, h = x1 - x0, y1 - y0
    if h < 6 or w < 10:
        return
    kieu = "cong_vien" if lon else rng.choice(["cong_vien", "san_the_thao", "vuon_rau", "vuon_cay", "cong_vien"])
    if kieu == "cong_vien":
        _to(nen, S, (92, 146, 92), x0, y0, x1, y1)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (min(w * 0.30, 30.0), min(h * 0.30, 16.0)) if lon else (min(w * 0.22, 9.0), min(h * 0.30, 6.0))
        e = pygame.Rect(round((cx - rx) * S), round((cy - ry) * S), round(2 * rx * S), round(2 * ry * S))
        pygame.draw.ellipse(nen, (214, 205, 176), e.inflate(round(1.6 * S), round(1.6 * S)))   # lối đi
        pygame.draw.ellipse(nen, (104, 170, 208), e)                                           # hồ nước
        pygame.draw.ellipse(nen, (150, 205, 230), e.inflate(-round(2 * S), -round(2 * S)), max(1, round(0.3 * S)))
        for _ in range(int(w * h / 90)):
            tx, ty = rng.uniform(x0 + 1.5, x1 - 1.5), rng.uniform(y0 + 1.5, y1 - 1.5)
            if ((tx - cx) / (rx + 2.5)) ** 2 + ((ty - cy) / (ry + 2.5)) ** 2 >= 1:   # không trồng cây giữa hồ
                ds_cay.append((tx, ty, rng.uniform(1.1, 1.9)))
    elif kieu == "san_the_thao":
        sw, sh = min(w - 4, 28.0), min(h - 2, 15.0)
        sx, sy = (x0 + x1) / 2 - sw / 2, (y0 + y1) / 2 - sh / 2
        _to(nen, S, (190, 190, 196), sx - 1, sy - 1, sx + sw + 1, sy + sh + 1)
        _to(nen, S, (74, 124, 170), sx, sy, sx + sw, sy + sh)
        for xa, ya, xb, yb in ((sx + 0.3, sy + 0.3, sx + sw - 0.3, sy + 0.3),
                               (sx + 0.3, sy + sh - 0.3, sx + sw - 0.3, sy + sh - 0.3),
                               (sx + 0.3, sy + 0.3, sx + 0.3, sy + sh - 0.3),
                               (sx + sw - 0.3, sy + 0.3, sx + sw - 0.3, sy + sh - 0.3),
                               (sx + sw / 2, sy + 0.3, sx + sw / 2, sy + sh - 0.3)):
            _net(nen, S, (235, 235, 240), (xa, ya), (xb, yb), 0.18)
        pygame.draw.circle(nen, (235, 235, 240), _px(S, sx + sw / 2, sy + sh / 2), round(2.2 * S), max(1, round(0.18 * S)))
        for _ in range(int(w / 7)):
            ds_cay.append((rng.uniform(x0 + 1, x1 - 1), rng.choice([y0 + 1.0, y1 - 1.0]), rng.uniform(1.0, 1.5)))
    elif kieu == "vuon_rau":
        _to(nen, S, (120, 92, 62), x0 + 1, y0 + 0.5, x1 - 1, y1 - 0.5)
        y, i = y0 + 1.2, 0
        while y + 1.4 < y1 - 0.5:
            _to(nen, S, (86, 150, 70) if i % 2 == 0 else (110, 170, 80), x0 + 1.6, y, x1 - 1.6, y + 1.4)
            y += 2.4
            i += 1
    else:                                           # vườn cây
        for _ in range(int(w * h / 55)):
            ds_cay.append((rng.uniform(x0 + 1.2, x1 - 1.2), rng.uniform(y0 + 1.2, y1 - 1.2), rng.uniform(1.2, 2.0)))


def ve_sieu_thi(nen, S, rng, x0, y0, x1, y1, font_bien, ds_cay):
    """SIÊU THỊ: tòa nhà mái phẳng có biển hiệu, cửa kính + mái hiên ở mặt Nam, bãi đỗ xe có
    kẻ vạch, xe đỗ sẵn, lối ra đường. (x0..y1: lô đất, mét)"""
    w = x1 - x0
    bw, bh = min(46.0, w - 6.0), 20.0
    bx, by = x0 + (w - bw) / 2, y0 + 2.5

    # Bóng + thân tòa nhà + mái + dải màu thương hiệu phía mặt tiền (Nam)
    _to(nen, S, _toi(MAU_DAT_THO, 0.7), bx + 1.2, by + 1.2, bx + bw + 1.2, by + bh + 1.2)
    _to(nen, S, (170, 174, 182), bx, by, bx + bw, by + bh)
    _to(nen, S, (214, 218, 224), bx + 0.5, by + 0.5, bx + bw - 0.5, by + bh - 0.5)
    _to(nen, S, (218, 62, 52), bx + 0.5, by + bh - 4.0, bx + bw - 0.5, by + bh - 0.5)
    _to(nen, S, (250, 200, 60), bx + 0.5, by + bh - 4.4, bx + bw - 0.5, by + bh - 4.0)
    # Giếng trời + máy lạnh trên mái
    for i in range(5):
        sx = bx + 4 + i * (bw - 8) / 4.0 - 1.5
        _to(nen, S, (170, 214, 236), sx, by + 2.0, sx + 3.0, by + 4.2)
    for i in range(4):
        ax = bx + 5 + i * (bw - 10) / 3.0 - 1.2
        _to(nen, S, (140, 144, 152), ax, by + 13.0, ax + 2.4, by + 15.0)
        _to(nen, S, (110, 114, 122), ax + 0.4, by + 13.4, ax + 2.0, by + 14.6)
    chu = font_bien.render("SIÊU THỊ", True, (200, 40, 40))
    nen.blit(chu, chu.get_rect(center=_px(S, bx + bw / 2, by + 8.3)))
    # Cửa kính tự động + mái hiên
    cw, cxm = 10.0, bx + bw / 2
    _to(nen, S, (126, 196, 232), cxm - cw / 2, by + bh - 0.1, cxm + cw / 2, by + bh + 0.7)
    _to(nen, S, (150, 40, 36), cxm - cw / 2 - 1.0, by + bh + 0.7, cxm + cw / 2 + 1.0, by + bh + 2.6)
    _to(nen, S, (250, 200, 60), cxm - cw / 2 - 1.0, by + bh + 2.6, cxm + cw / 2 + 1.0, by + bh + 3.0)

    # Bãi đỗ xe + lối ra đường phía Nam (cắt qua vỉa hè)
    py0, py1 = by + bh + 3.6, y1 - 0.4
    px0, px1 = x0 + 0.8, x1 - 0.8
    _to(nen, S, (176, 178, 184), px0 - 0.3, py0 - 0.3, px1 + 0.3, py1 + 0.3)
    _to(nen, S, (66, 68, 76), px0, py0, px1, py1)
    _to(nen, S, (66, 68, 76), (px0 + px1) / 2 - 3.5, py1, (px0 + px1) / 2 + 3.5, y1 + 2.4)
    # Các dãy chỗ đỗ: 2 cặp dãy lưng đối lưng
    cao_bai, dai_xe, rong_cho = py1 - py0, 4.6, 2.7
    hang_y = []
    if cao_bai >= 2 * dai_xe + 2.0:
        hang_y += [py0 + 0.8, py0 + 0.8 + dai_xe]
    if cao_bai >= 4 * dai_xe + 9.0:
        y2 = py1 - 0.8 - 2 * dai_xe
        hang_y += [y2, y2 + dai_xe]
    for ry in hang_y:
        x = px0 + 1.2
        while x + rong_cho <= px1 - 1.2:
            _net(nen, S, (222, 222, 228), (x, ry), (x, ry + dai_xe), 0.14)
            if rng.random() < 0.58:
                mau = rng.choice(MAU_XE)
                _to(nen, S, mau, x + 0.35, ry + 0.4, x + rong_cho - 0.35, ry + dai_xe - 0.4)
                _to(nen, S, _toi(mau, 0.35), x + 0.55, ry + 1.3, x + rong_cho - 0.55, ry + 2.4)
            x += rong_cho
    # Biển P, nơi để xe đẩy, cây hai bên tòa nhà
    _to(nen, S, (50, 100, 190), px0 + 0.5, py1 - 3.0, px0 + 2.7, py1 - 0.8)
    p = font_bien.render("P", True, (255, 255, 255))
    p = pygame.transform.smoothscale(p, (max(1, p.get_width() // 3), max(1, p.get_height() // 3)))
    nen.blit(p, p.get_rect(center=_px(S, px0 + 1.6, py1 - 1.9)))
    for i in range(3):
        _to(nen, S, (150, 154, 162), bx + 1.5, by + bh + 1.0 + i * 0.9, bx + 6.0, by + bh + 1.5 + i * 0.9)
    for tx in (x0 + 1.8, x1 - 1.8):
        for ty in (by + 2.0, by + 9.0, by + 16.0):
            ds_cay.append((tx, ty, 1.5))


def _cac_doan(tong, toa_do_nut, bo):
    """Chia một con đường dài `tong` mét thành các đoạn, cắt bỏ các khoảng giữa 2 ngã tư trong `bo`."""
    doan, dau = [], 0.0
    for a, b in sorted(bo):
        doan.append((dau, toa_do_nut[a]))
        dau = toa_do_nut[b]
    return doan + [(dau, tong)]


def _gop_o_pho():
    """Gộp các ô phố nằm hai bên một đoạn đường bị bỏ thành một ô lớn.
    Trả về (danh sách ô: dict ic0/ic1/ir0/ir1/tap, ô siêu thị). Ô phố (ic, ir): cột/hàng giữa các đường."""
    nhom = {(ic, ir): {(ic, ir)} for ic in range(SO_COT + 1) for ir in range(SO_HANG + 1)}

    def gop(a, b):
        hop = nhom[a] | nhom[b]
        for k in hop:
            nhom[k] = hop

    for lk in LIEN_KET_BO:
        (r1, c1), (r2, c2) = sorted(lk)
        if r1 == r2:                         # đường ngang bị bỏ: gộp ô phía trên với ô phía dưới
            gop((c2, r1), (c2, r1 + 1))
        else:                                # đường dọc bị bỏ: gộp ô bên trái với ô bên phải
            gop((c1, r2), (c1 + 1, r2))
    o_phos, da_co = [], set()
    for k, tap in nhom.items():
        if k in da_co:
            continue
        da_co |= tap
        ics, irs = [a for a, _ in tap], [b for _, b in tap]
        if len(tap) != (max(ics) - min(ics) + 1) * (max(irs) - min(irs) + 1):
            raise ValueError("Các đoạn đường bị bỏ nằm quá sát nhau, ô phố gộp không còn là hình chữ nhật")
        o_phos.append({"ic0": min(ics), "ic1": max(ics), "ir0": min(irs), "ir1": max(irs), "tap": tap})
    o_sieu_thi = (SO_COT // 2, SO_HANG // 2)          # ô chính giữa bản đồ
    if len(nhom[o_sieu_thi]) > 1:
        raise ValueError("Không được bỏ đoạn đường bao quanh siêu thị")
    return o_phos, o_sieu_thi


def ve_nen_chi_tiet(S, font_bien_goc):
    """Vẽ toàn bộ bản đồ tĩnh ở độ phân giải S (pixel/mét): cỏ, vỉa hè, đường, vạch kẻ, vạch
    qua đường, nhà ở, cây, công viên và siêu thị."""
    nen = pygame.Surface((int(RONG_M * S), int(CAO_M * S)))
    nen.fill(MAU_CO)
    rng = random.Random(2024)               # cố định để lần nào chạy cũng giống nhau
    ds_cay = []                             # cây vẽ SAU CÙNG để che lên nhà/sân
    VH = 2.2                                # bề rộng vỉa hè

    # Ranh giới các "ô phố" nằm giữa các đường (5 x 5 ô, ô ngoài cùng bị cắt bởi mép bản đồ)
    lo_x = [0.0] + [CX[c] + NUA_DUONG for c in range(SO_COT)]
    hi_x = [CX[c] - NUA_DUONG for c in range(SO_COT)] + [RONG_M]
    lo_y = [0.0] + [CY[r] + NUA_DUONG for r in range(SO_HANG)]
    hi_y = [CY[r] - NUA_DUONG for r in range(SO_HANG)] + [CAO_M]
    o_phos, o_sieu_thi = _gop_o_pho()

    def khung_o(o):
        """Toạ độ ô phố (x0, y0, x1, y1) và phần đất bên trong sau khi chừa vỉa hè."""
        x0, x1 = lo_x[o["ic0"]], hi_x[o["ic1"]]
        y0, y1 = lo_y[o["ir0"]], hi_y[o["ir1"]]
        return ((x0, y0, x1, y1),
                (x0 + (0 if o["ic0"] == 0 else VH), y0 + (0 if o["ir0"] == 0 else VH),
                 x1 - (0 if o["ic1"] == SO_COT else VH), y1 - (0 if o["ir1"] == SO_HANG else VH)))

    # --- 1. Vỉa hè + lô đất ---
    for o in o_phos:
        (x0, y0, x1, y1), (ix0, iy0, ix1, iy1) = khung_o(o)
        _to(nen, S, MAU_VIA_HE, x0, y0, x1, y1)
        _to(nen, S, MAU_DAT_THO, ix0, iy0, ix1, iy1)

    # --- 2. Mặt đường: vẽ theo từng ĐOẠN, bỏ qua đoạn nối đã bị bỏ ---
    # doan_duong: (nằm ngang?, tọa độ ngang/dọc cố định của đường, điểm đầu, điểm cuối)
    doan_duong = []
    for ngang, n, tam, doc, tong in ((True, SO_HANG, CY, CX, RONG_M), (False, SO_COT, CX, CY, CAO_M)):
        k = 1 if ngang else 0               # chỉ số "chạy dọc đường" trong cặp (hàng, cột)
        for i in range(n):
            bo = [(min(a[k], b[k]), max(a[k], b[k])) for a, b in map(tuple, LIEN_KET_BO) if a[1 - k] == b[1 - k] == i]
            doan_duong += [(ngang, tam[i], a, b) for a, b in _cac_doan(tong, doc, bo)]

    def diem(ngang, doc, ngang_cat):        # (tọa độ chạy dọc đường, tọa độ cắt ngang) -> (x, y)
        return (doc, ngang_cat) if ngang else (ngang_cat, doc)

    for ngang, t, a, b in doan_duong:
        _to(nen, S, MAU_DUONG, *diem(ngang, a, t - NUA_DUONG), *diem(ngang, b, t + NUA_DUONG))

    # --- 3. Vạch kẻ đường: vàng đôi ở giữa + nét đứt trắng giữa 2 làn (theo từng đoạn) ---
    for ngang, t, a, b in doan_duong:
        for dv in (-0.25, 0.25):
            _net(nen, S, (230, 190, 40), diem(ngang, a, t + dv), diem(ngang, b, t + dv), 0.16)
        for dv in (-LW, LW):
            u = a
            while u < b:
                _net(nen, S, (200, 200, 205), diem(ngang, u, t + dv), diem(ngang, min(u + 1.8, b), t + dv), 0.12)
                u += 3.6

    # --- 4. Ô giao nhau + vạch qua đường (zebra) ở các nhánh CÒN ĐƯỜNG của mỗi ngã tư ---
    for r in range(SO_HANG):
        for c in range(SO_COT):
            _to(nen, S, MAU_DUONG, CX[c] - NUA_DUONG, CY[r] - NUA_DUONG, CX[c] + NUA_DUONG, CY[r] + NUA_DUONG)
    for r in range(SO_HANG):
        for c in range(SO_COT):
            for h in range(4):
                if not co_duong(r, c, (h + 2) % 4):          # nhánh này không còn đường
                    continue
                d, lat = DIR[h], LAT[h]
                hx, hy = (0.4 if d[0] == 0 else 1.1), (0.4 if d[1] == 0 else 1.1)
                u = -NUA_DUONG + 0.8
                while u <= NUA_DUONG - 0.8:
                    # sọc nằm giữa mép ô giao (6.4 m) và vạch dừng (9.6 m)
                    gx = CX[c] - d[0] * (NUA_DUONG + 1.7) + lat[0] * u
                    gy = CY[r] - d[1] * (NUA_DUONG + 1.7) + lat[1] * u
                    _to(nen, S, (226, 226, 230), gx - hx, gy - hy, gx + hx, gy + hy)
                    u += 1.4

    # --- 5. Cây hàng trên vỉa hè (tránh gần ngã tư để không che đèn) ---
    for o in o_phos:
        (x0, y0, x1, y1), _ = khung_o(o)
        co_tren, co_duoi = o["ir0"] > 0, o["ir1"] < SO_HANG
        co_trai, co_phai = o["ic0"] > 0, o["ic1"] < SO_COT
        t = x0 + 14
        while t < x1 - 14:
            if not any(abs(t - cxv) < 16 for cxv in CX):
                if co_tren:
                    ds_cay.append((t, y0 + 1.1, 1.2))
                if co_duoi:
                    ds_cay.append((t, y1 - 1.1, 1.2))
            t += 10.0
        t = y0 + 14
        while t < y1 - 14:
            if not any(abs(t - cyv) < 16 for cyv in CY):
                if co_trai:
                    ds_cay.append((x0 + 1.1, t, 1.2))
                if co_phai:
                    ds_cay.append((x1 - 1.1, t, 1.2))
            t += 10.0

    # --- 6. Nhà, sân, công viên, siêu thị trên từng ô phố (ô gộp => công viên lớn) ---
    font_bien = font_bien_goc(max(8, round(4.4 * S)))
    for o in o_phos:
        _, (ix0, iy0, ix1, iy1) = khung_o(o)
        if o["tap"] == {o_sieu_thi}:
            ve_sieu_thi(nen, S, rng, ix0, iy0, ix1, iy1, font_bien, ds_cay)
            continue
        d = 9.0                              # chừa 1.2 m mép đất, nhà quay mặt ra đường gần nhất
        ve_hang_nha(nen, S, rng, ix0, ix1, iy0 + 1.2, d, "B", ds_cay)
        ve_hang_nha(nen, S, rng, ix0, ix1, iy1 - 1.2 - d, d, "N", ds_cay)
        ve_vung_giua(nen, S, rng, ix0 + 1.5, iy0 + 1.2 + d + 3.0, ix1 - 1.5, iy1 - 1.2 - d - 3.0, ds_cay,
                     lon=len(o["tap"]) > 1)

    # --- 7. Cây vẽ sau cùng ---
    for x, y, r in ds_cay:
        ve_cay(nen, S, x, y, r)
    return nen


def tao_nen_nhieu_muc(font_bien_goc):
    """Vẽ ảnh nền ở độ phân giải cao nhất (TL*ZOOM_MAX px/m) rồi thu nhỏ thành các mức 1/2, 1/4
    để khi vẽ chỉ cần thu phóng nhẹ. Trả về danh sách [(pixel/mét, ảnh)] giảm dần."""
    s_max = TL * ZOOM_MAX
    top = ve_nen_chi_tiet(s_max, font_bien_goc)
    return [(s_max, top)] + [
        (s_max / chia, pygame.transform.smoothscale(top, (max(1, top.get_width() // chia),
                                                          max(1, top.get_height() // chia))))
        for chia in (2, 4)]


def ve_nen_len_man_hinh(man, nen_muc, cam, cache):
    """Cắt đúng phần bản đồ đang nhìn thấy, thu phóng về kích thước màn hình."""
    k = cam.k
    ung_vien = [m for m in nen_muc if m[0] >= k]
    px_l, anh = min(ung_vien, key=lambda m: m[0]) if ung_vien else nen_muc[0]
    sx = int(math.floor(-cam.px / k * px_l))
    sy = int(math.floor(-cam.py / k * px_l))
    sw = int(math.ceil(cam.vw / k * px_l)) + 2
    sh = int(math.ceil(cam.vh / k * px_l)) + 2
    nguon = pygame.Rect(sx, sy, sw, sh).clip(anh.get_rect())
    if nguon.w <= 0 or nguon.h <= 0:
        return
    khoa = (nguon.x, nguon.y, nguon.w, nguon.h, px_l, round(k, 3))
    if cache.get("khoa") != khoa:             # chỉ thu phóng lại khi camera đổi
        he = k / px_l
        kich = (max(1, round(nguon.w * he)), max(1, round(nguon.h * he)))
        cache["anh"] = pygame.transform.smoothscale(anh.subsurface(nguon), kich)
        cache["khoa"] = khoa
    man.blit(cache["anh"], (round(cam.px + nguon.x / px_l * k), round(cam.py + nguon.y / px_l * k)))


# ==========================================================================
# PHẦN 8. ĐỒ HỌA ĐỘNG: ĐÈN, XE, BẢN ĐỒ NHỎ, BẢNG THÔNG TIN
# ==========================================================================

def tao_font(co, dam=False):
    """Chọn font hỗ trợ tiếng Việt có trên máy."""
    for ten in ("segoeui", "arial", "tahoma", "dejavusans", "freesans", "liberationsans"):
        duong_dan = pygame.font.match_font(ten, bold=dam)
        if duong_dan:
            return pygame.font.Font(duong_dan, co)
    return pygame.font.Font(None, co + 6)


_CHU_CACHE = {}


def chu_cache(font, text, mau):
    """Render chữ có nhớ đệm (tránh vẽ lại chữ giống nhau mỗi khung hình)."""
    khoa = (id(font), text, mau)
    if khoa not in _CHU_CACHE:
        if len(_CHU_CACHE) > 600:
            _CHU_CACHE.clear()
        _CHU_CACHE[khoa] = font.render(text, True, mau)
    return _CHU_CACHE[khoa]


def viet_chu(man, font, text, mau, vi_tri, giua=False):
    """Vẽ chữ tại vi_tri (góc trên-trái, hoặc tâm nếu giua=True)."""
    chu = font.render(text, True, mau)
    man.blit(chu, chu.get_rect(center=vi_tri) if giua else vi_tri)


def viet_doan(man, font, text, mau, x, y, rong, cach=17):
    """Vẽ đoạn văn tự xuống dòng trong bề rộng `rong` pixel."""
    for i, dong in enumerate(bo_chu(font, text, rong)):
        viet_chu(man, font, dong, mau, (x, y + i * cach))


def _hcn(cx, cy, dx, dy, hl, hw):
    """4 đỉnh hình chữ nhật tâm (cx, cy), nửa dài hl theo hướng (dx, dy), nửa rộng hw."""
    lx, ly = -dy, dx
    return [(cx + dx * hl * a + lx * hw * b, cy + dy * hl * a + ly * hw * b)
            for a, b in ((1, 1), (1, -1), (-1, -1), (-1, 1))]


def goc_cn(cam, tam, d, dai, rong):
    """4 đỉnh (pixel màn hình) của hình chữ nhật có tâm `tam` (mét), trục theo d."""
    return [(x * cam.k + cam.px, y * cam.k + cam.py)
            for x, y in _hcn(tam[0], tam[1], d[0], d[1], dai / 2, rong / 2)]


def ve_nut(man, mp, nut, f_nho, f_tb, chon, cam):
    """Vạch dừng đổi màu theo đèn, đèn bên đường có đếm ngược, nhãn tên + pha."""
    k, t = cam.k, mp.t
    sx, sy = cam.sang_man_hinh(nut.cx, nut.cy)
    bien = 22 * k
    if not (-bien <= sx <= cam.vw + bien and -bien <= sy <= cam.vh + bien):
        return                                       # ngã tư nằm ngoài khung nhìn

    moc = nut.ke_hoach.moc
    for h in range(4):
        if not co_duong(nut.r, nut.c, (h + 2) % 4):   # nhánh này không còn đường: không có đèn
            continue
        d, lat = DIR[h], LAT[h]
        goc_x, goc_y = nut.cx - d[0] * VACH, nut.cy - d[1] * VACH
        for lan, loai in ((0, "Re"), (1, "Th")):     # làn trong = rẽ trái, làn ngoài = đi thẳng
            khoa = NHAN[h] + "_" + loai
            if khoa in moc:                           # dòng xe này có ở ngã tư này
                tam = (goc_x + lat[0] * OFF[lan], goc_y + lat[1] * OFF[lan])
                pygame.draw.polygon(man, MAU_DEN[nut.trang_thai(khoa, t)], goc_cn(cam, tam, d, 0.9, LW * 0.92))

        khoa = next((kk for kk in (NHAN[h] + "_Th", NHAN[h] + "_Re") if kk in moc), None)
        if khoa is None:
            continue
        den = nut.trang_thai(khoa, t)
        giay = nut.ke_hoach.con_lai(khoa, nut.u(t))
        vx = goc_x - d[0] * 1.8 + lat[0] * (NUA_DUONG + 1.8)
        vy = goc_y - d[1] * 1.8 + lat[1] * (NUA_DUONG + 1.8)
        pt = cam.sang_man_hinh(vx, vy)
        pygame.draw.circle(man, (20, 20, 24), pt, max(3, int(2.0 * k)))
        pygame.draw.circle(man, MAU_DEN[den], pt, max(2, int(1.5 * k)))
        if cam.zoom >= 0.85:
            chu = chu_cache(f_nho, str(int(giay) + 1), (255, 255, 255))
            man.blit(chu, chu.get_rect(center=cam.sang_man_hinh(vx + lat[0] * 3.6, vy + lat[1] * 3.6)))

    pha = nut.ke_hoach.pha_hien_tai(nut.u(t))
    mau_pha = MAU_PHA[pha % 4]
    hop = pygame.Rect(0, 0, 8 * k, 8 * k)
    hop.center = (sx, sy)
    pygame.draw.rect(man, (30, 32, 38), hop, border_radius=max(2, int(k)))
    pygame.draw.rect(man, mau_pha, hop, max(1, int(0.5 * k)), border_radius=max(2, int(k)))
    c1 = chu_cache(f_tb, nut.ten, MAU_BLOCK[nut.block])
    if cam.zoom >= 0.85:
        man.blit(c1, c1.get_rect(center=(sx, sy - 0.2 * k * 2.2)))
        c2 = chu_cache(f_nho, f"P{pha + 1}", mau_pha)
        man.blit(c2, c2.get_rect(center=(sx, sy + 2.3 * k)))
    else:
        man.blit(c1, c1.get_rect(center=(sx, sy)))
    if chon:
        vien = pygame.Rect(0, 0, (2 * NUA_DUONG + 2) * k, (2 * NUA_DUONG + 2) * k)
        vien.center = (sx, sy)
        pygame.draw.rect(man, (255, 255, 255), vien, 2)


def ve_xe(man, xe, cam):
    """Xe là hình chữ nhật xoay theo hướng, có kính chắn gió và đèn phanh."""
    k = cam.k
    x, y = xe.vi_tri()
    sx, sy = x * k + cam.px, y * k + cam.py
    if not (-30 <= sx <= cam.vw + 30 and -30 <= sy <= cam.vh + 30):
        return                                       # ngoài khung nhìn: bỏ qua
    a = math.radians(xe.goc)
    dx, dy = math.cos(a), math.sin(a)
    L, W = XE_DAI * k, (XE_RONG + 0.2) * k
    cx, cy = sx - dx * L / 2, sy - dy * L / 2        # tâm xe (sx, sy là đầu xe)
    hl, hw = L / 2, W / 2
    pygame.draw.polygon(man, xe.mau, _hcn(cx, cy, dx, dy, hl, hw))
    if k >= 2.6:                                     # kính chắn gió
        pygame.draw.polygon(man, (35, 45, 60), _hcn(cx + dx * L * 0.2, cy + dy * L * 0.2, dx, dy, L * 0.11, hw * 0.8))
    if k >= 3.0 and (xe.a < -0.5 or xe.v < 0.3):     # đèn phanh
        lx, ly = -dy, dx
        for b in (-1, 1):
            pygame.draw.circle(man, (255, 40, 40), (cx - dx * hl + lx * b * hw * 0.7, cy - dy * hl + ly * b * hw * 0.7),
                               max(1, int(k * 0.5)))


def ten_pha(pha):
    huong = "+".join(TEN_HUONG[k[0]] for k in pha)
    if all(k.endswith("Th") for k in pha):
        return huong + " đi thẳng"
    if all(k.endswith("Re") for k in pha):
        return huong + " rẽ trái"
    return huong


def bo_chu(font, text, rong):
    """Ngắt một đoạn văn thành nhiều dòng sao cho mỗi dòng không rộng quá `rong` pixel."""
    dong, cur = [], ""
    for tu in text.split():
        thu = (cur + " " + tu).strip()
        if font.size(thu)[0] <= rong:
            cur = thu
        else:
            if cur:
                dong.append(cur)
            cur = tu
    return dong + [cur] if cur else dong


def ten_dong_xe(khoa):
    """'B_Th' -> ('Bắc', 'đi thẳng')."""
    return TEN_HUONG[khoa[0]], ("đi thẳng" if khoa.endswith("Th") else "rẽ trái")


_SAC_DO = {}


def so_sac_do(do_thi):
    """Số sắc độ của đồ thị xung đột (tìm bằng quay lui của code lõi, nhớ kết quả)."""
    khoa = tuple(sorted((u, tuple(sorted(v))) for u, v in do_thi.items()))
    if khoa not in _SAC_DO:
        _SAC_DO[khoa] = max(loi.to_mau_quay_lui(do_thi).values()) + 1
    return _SAC_DO[khoa]


def ve_do_thi_xung_dot(man, mp, nut, fonts, vw, vh, chuot):
    """
    Cửa sổ ĐỒ THỊ XUNG ĐỘT + TÔ MÀU (bấm G để mở/đóng).
    Cách đọc:
      - Mỗi ĐỈNH (hình tròn) là một dòng xe, tô màu theo PHA của nó; các đỉnh CÙNG MÀU gom
        vào một khung = một pha đèn xanh.
      - Mỗi CẠNH nối 2 dòng xe sẽ va chạm nếu đi cùng lúc.
      - Rê chuột vào một đỉnh để làm nổi bật các cạnh/xung đột của nó (nếu không rê chuột,
        chương trình tự đổi đỉnh mỗi ~2 giây).  Chấm nhỏ cạnh mỗi đỉnh = màu đèn hiện tại.
    """
    f_to, f_tb, f_nho = fonts
    w, h = min(vw - 24, 800), min(vh - 24, 600)
    x0, y0 = (vw - w) // 2, (vh - h) // 2
    hop = pygame.Surface((w, h), pygame.SRCALPHA)
    hop.fill((16, 19, 27, 248))
    man.blit(hop, (x0, y0))
    pygame.draw.rect(man, (100, 140, 255), (x0, y0, w, h), 2, border_radius=10)
    viet_chu(man, f_to, f"ĐỒ THỊ XUNG ĐỘT & TÔ MÀU  ·  NÚT {nut.ten}", (255, 255, 255), (x0 + 18, y0 + 12))

    kh = nut.ke_hoach
    do_thi = kh.do_thi                       # đồ thị riêng của ngã tư này (ngã ba thì ít đỉnh hơn)
    mau_cua = {k: i for i, pha in enumerate(kh.cac_pha) for k in pha}     # đỉnh -> màu (chỉ số pha)

    viet_doan(man, f_nho, "Mỗi ĐỈNH là một dòng xe. Hai đỉnh nối bằng CẠNH nghĩa là hai dòng xe sẽ va chạm "
              "nếu đi cùng lúc, nên phải khác MÀU. Các đỉnh cùng màu được nhóm thành một PHA và cùng được "
              "đèn xanh.", (170, 182, 205), x0 + 18, y0 + 42, w - 36)

    # --- Vùng vẽ đồ thị (trái) và bảng giải thích (phải) ---
    RP = 250
    gx, gy = x0 + 16, y0 + 92
    gw, gh = w - 32 - RP - 12, h - 92 - 52
    cot, hang, khoang = 2, (len(kh.cac_pha) + 1) // 2, 14
    bw, bh = (gw - khoang) / cot, (gh - khoang * (hang - 1)) / hang

    # Vị trí đỉnh: mỗi pha là một khung, các đỉnh của pha nằm ngang hàng trong khung
    vi_tri, khung = {}, []
    for i, pha in enumerate(kh.cac_pha):
        bx = gx + (i % cot) * (bw + khoang)
        by = gy + (i // cot) * (bh + khoang)
        khung.append(pygame.Rect(bx, by, bw, bh))
        for j, k in enumerate(pha):
            # so le lên/xuống để cạnh nối không đi xuyên qua một đỉnh khác nằm thẳng hàng
            vi_tri[k] = (bx + bw * (j + 1) / (len(pha) + 1), by + bh * (0.44 if j % 2 == 0 else 0.62))

    # Đỉnh đang được nhấn mạnh: theo chuột, nếu không có thì tự đổi
    bk = 26
    nhan_manh, tu_dong = None, False
    for k, (px_, py_) in vi_tri.items():
        if (chuot[0] - px_) ** 2 + (chuot[1] - py_) ** 2 <= (bk + 4) ** 2:
            nhan_manh = k
    if nhan_manh is None:
        ds = [k for pha in kh.cac_pha for k in pha]
        nhan_manh, tu_dong = ds[(pygame.time.get_ticks() // 2200) % len(ds)], True
    ke_nhan_manh = do_thi[nhan_manh]

    # 1) Khung từng pha (đỉnh cùng màu), sáng lên nếu pha đang xanh/vàng
    for i, (r_, pha) in enumerate(zip(khung, kh.cac_pha)):
        mau = MAU_PHA[i % len(MAU_PHA)]
        trang = [nut.trang_thai(k, mp.t) for k in pha]
        dang = "G" if "G" in trang else ("Y" if "Y" in trang else "R")
        pygame.draw.rect(man, (26, 30, 42), r_, border_radius=8)
        pygame.draw.rect(man, MAU_DEN[dang] if dang != "R" else mau, r_, 3 if dang != "R" else 2, border_radius=8)
        viet_chu(man, f_nho, f"PHA {i + 1}  ·  xanh {kh.xanh[i]}s  ·  dừng {kh.dung[i]}s", mau, (r_.x + 10, r_.y + 8))
        if dang != "R":
            chu = f_nho.render("XANH" if dang == "G" else "VÀNG", True, (20, 22, 28))
            nen_the = pygame.Rect(0, 0, chu.get_width() + 12, chu.get_height() + 2)
            nen_the.topright = (r_.right - 8, r_.y + 7)                # góc trên phải
            pygame.draw.rect(man, MAU_DEN[dang], nen_the, border_radius=4)
            man.blit(chu, (nen_the.x + 6, nen_the.y + 1))

    # 2) Cạnh: mờ cho tất cả, đậm đỏ cho các cạnh của đỉnh đang nhấn mạnh
    da_ve = set()
    for u, ke in do_thi.items():
        for v in ke:
            canh = tuple(sorted((u, v)))
            if canh not in da_ve and nhan_manh not in canh:
                da_ve.add(canh)
                pygame.draw.line(man, (58, 64, 84), vi_tri[u], vi_tri[v], 1)
    for v in ke_nhan_manh:
        pygame.draw.line(man, (255, 105, 85), vi_tri[nhan_manh], vi_tri[v], 4)

    # 3) Đỉnh: tô màu theo pha, viền trắng = đang xem, viền đỏ = xung đột với đỉnh đang xem
    for k, (px_, py_) in vi_tri.items():
        pygame.draw.circle(man, MAU_PHA[mau_cua[k] % len(MAU_PHA)], (px_, py_), bk)
        if k == nhan_manh:
            pygame.draw.circle(man, (255, 255, 255), (px_, py_), bk + 3, 3)
        elif k in ke_nhan_manh:
            pygame.draw.circle(man, (255, 105, 85), (px_, py_), bk + 3, 3)
        else:
            pygame.draw.circle(man, (14, 16, 22), (px_, py_), bk, 2)
        viet_chu(man, f_tb, k, (14, 16, 22), (px_, py_), giua=True)
        huong, kieu = ten_dong_xe(k)
        viet_chu(man, f_nho, huong, (235, 238, 245), (px_, py_ + bk + 12), giua=True)
        viet_chu(man, f_nho, kieu, (160, 170, 190), (px_, py_ + bk + 28), giua=True)
        cham = (px_ + bk - 4, py_ - bk + 4)                            # chấm đèn hiện tại
        pygame.draw.circle(man, (14, 16, 22), cham, 8)
        pygame.draw.circle(man, MAU_DEN[nut.trang_thai(k, mp.t)], cham, 6)

    # --- Bảng giải thích bên phải ---
    rx, ry = x0 + w - RP - 14, gy
    pygame.draw.rect(man, (26, 30, 42), (rx - 6, ry, RP + 6, gh), border_radius=8)
    ty = ry + 10

    def viet(text, font=f_nho, mau=(215, 220, 232), dx=0):
        nonlocal ty
        for dong in bo_chu(font, text, RP - 18 - dx):
            viet_chu(man, font, dong, mau, (rx + 4 + dx, ty))
            ty += font.get_height() + 2

    def viet_ds(dong_xe, dx=18):
        for v in dong_xe:
            hv, kv = ten_dong_xe(v)
            viet(f"{hv} {kv}", f_nho, (215, 220, 232), dx=dx)

    huong, kieu = ten_dong_xe(nhan_manh)
    viet("ĐANG XEM" + ("  (tự đổi mỗi 2 giây)" if tu_dong else "  (theo chuột)"), f_nho, (140, 190, 255))
    viet(f"{nhan_manh}: {huong} {kieu}", f_tb, (255, 255, 255))
    viet(f"Xung đột với {len(ke_nhan_manh)} dòng xe (nối bằng cạnh đỏ):", f_nho, (255, 140, 120))
    for v in sorted(ke_nhan_manh):
        pygame.draw.rect(man, MAU_PHA[mau_cua[v] % len(MAU_PHA)], (rx + 6, ty + 3, 8, 8))
        viet_ds([v])
    cung = [k for k in kh.cac_pha[mau_cua[nhan_manh]] if k != nhan_manh]
    ty += 4
    if cung:
        viet("Đi chung được (cùng màu, không nối nhau):", f_nho, (130, 230, 150))
        viet_ds(cung)

    ty = max(ty + 8, ry + gh - 118)
    pygame.draw.line(man, (60, 66, 84), (rx, ty - 6), (rx + RP - 12, ty - 6), 1)
    so_canh = sum(len(v) for v in do_thi.values()) // 2
    hop_le = loi.kiem_tra_to_mau_hop_le(do_thi, mau_cua)
    viet("KẾT QUẢ TÔ MÀU", f_nho, (140, 190, 255))
    viet(f"{len(do_thi)} đỉnh · {so_canh} cạnh · dùng {len(kh.cac_pha)} màu", f_nho)
    viet(f"Số màu tối thiểu (sắc độ) = {so_sac_do(do_thi)}", f_nho)
    viet("✓ Hợp lệ: không cạnh nào nối 2 đỉnh cùng màu" if hop_le else "✗ Không hợp lệ!", f_nho,
         (130, 230, 150) if hop_le else (255, 110, 110))

    viet_doan(man, f_nho, "Viền trắng = đỉnh đang xem · viền & cạnh đỏ = xung đột · chấm nhỏ = đèn hiện tại · "
              "Rê chuột vào đỉnh để xem · Phím G: đóng", (130, 140, 160), x0 + 18, y0 + h - 40, w - 36)


def ve_bang(man, mp, fonts, nut_chon, toc_do, tam_dung, cam):
    """Bảng thông tin bên phải: chế độ, thống kê, kế hoạch đèn 16 ngã tư."""
    f_to, f_tb, f_nho = fonts
    x0, cao = cam.vw, man.get_height()
    pygame.draw.rect(man, (24, 26, 32), (x0, 0, RONG_BANG, cao))
    pygame.draw.line(man, (70, 74, 86), (x0, 0), (x0, cao), 1)
    x, y = x0 + 12, 8

    def dong(text, font=f_tb, mau=(225, 228, 235), dx=0):
        nonlocal y
        viet_chu(man, font, text, mau, (x + dx, y))
        y += font.get_height() + 2

    dong("MÔ PHỎNG ĐÈN GIAO THÔNG", f_to, (255, 255, 255))
    dong(f"Hệ thống 2x2 block · {len(mp.ds_nut)} ngã tư, đủ {len(mp.ds_nut)} đèn", f_nho, (160, 170, 190))
    toi_uu = mp.che_do == "toi_uu"
    mau_cd = (110, 235, 140) if toi_uu else (255, 190, 90)
    dong("Chế độ: " + ("TỐI ƯU (Webster)" if toi_uu else "CỐ ĐỊNH 60s (chia đều)"), f_tb, mau_cd)
    phut, giay = divmod(int(mp.t), 60)
    dong(f"{phut:02d}:{giay:02d}  ·  Tốc độ x{toc_do}  ·  Zoom {int(cam.zoom * 100)}%"
         + ("  [TẠM DỪNG]" if tam_dung else ""), f_nho, (170, 176, 190))

    y += 4
    dong("THỐNG KÊ (đo trong mô phỏng)", f_nho, (140, 190, 255))
    n, dung, _ = mp.thong_ke()
    dong(f"Xe trong khu vực: {len(mp.xe)}   đang dừng: {sum(1 for xe in mp.xe if xe.v < 0.3)}", f_nho)
    dong(f"Xe đã đi qua: {n}", f_nho)
    dong(f"Thời gian dừng TB: {dung:.1f} giây/xe", f_nho, mau_cd)
    for kk, ten in (("toi_uu", "Tối ưu"), ("co_dinh", "Cố định")):
        n2, d2, _ = mp.thong_ke(kk)
        dong(f"{ten}: {d2:.1f} s/xe ({n2} xe)" if n2 else f"{ten}: chưa đo", f_nho, (170, 176, 190), dx=8)

    y += 4
    dong(f"KẾ HOẠCH ĐÈN {len(mp.ds_nut)} NGÃ TƯ (code lõi)", f_nho, (140, 190, 255))
    bw = RONG_BANG - 24 - 150
    for nut in mp.ds_nut:
        kh = nut.ke_hoach
        chon = nut is nut_chon
        if chon:
            pygame.draw.rect(man, (60, 66, 84), (x - 4, y - 1, RONG_BANG - 16, 17), border_radius=3)
        pygame.draw.rect(man, MAU_BLOCK[nut.block], (x, y + 4, 6, 8))
        viet_chu(man, f_nho, f"{nut.ten} {kh.chu_ky}s{'!' if kh.qua_tai else ''} " + "|".join(str(g) for g in kh.xanh),
                 (255, 255, 255) if chon else (200, 204, 214), (x + 11, y))
        bx, by, a = x + 150, y + 4, 0.0                 # thanh các pha trong 1 chu kỳ
        for i, g in enumerate(kh.xanh):
            w = (g + kh.mat) / kh.chu_ky * bw
            pygame.draw.rect(man, MAU_PHA[i % 4], (bx + a, by, max(1, w - 1), 7))
            pygame.draw.rect(man, (40, 40, 46), (bx + a + g / kh.chu_ky * bw, by, max(1, kh.mat / kh.chu_ky * bw), 7))
            a += w
        cur = nut.u(mp.t) / kh.chu_ky * bw              # vạch trắng = thời điểm hiện tại
        pygame.draw.line(man, (255, 255, 255), (bx + cur, by - 2), (bx + cur, by + 9), 2)
        y += 17

    y += 6
    kh = nut_chon.ke_hoach
    dong(f"CHI TIẾT NÚT {nut_chon.ten}  (xanh / dừng)", f_nho, (140, 190, 255))
    pha_ht = kh.pha_hien_tai(nut_chon.u(mp.t))
    for i, pha in enumerate(kh.cac_pha):
        pygame.draw.rect(man, MAU_PHA[i % 4], (x, y + 4, 8, 8))
        dong(f"P{i + 1} {ten_pha(pha)}: {kh.xanh[i]}s / {kh.dung[i]}s", f_nho,
             (255, 255, 255) if i == pha_ht else (170, 176, 190), dx=14)

    for i, t in enumerate(("SPACE: dừng | M: đổi chế độ | G: đồ thị",
                           "Cuộn/+-: zoom | Chuột phải/WASD: lia | 0: toàn cảnh",
                           "Click/TAB/1-4: chọn nút | ↑↓: tốc độ | R: làm lại")):
        viet_chu(man, f_nho, t, (130, 136, 150), (x, cao - 70 + i * 18))


# ==========================================================================
# PHẦN 9. VÒNG LẶP CHÍNH
# ==========================================================================

def man_hinh_cho(man, f_to, thong_bao):
    man.fill((24, 26, 32))
    viet_chu(man, f_to, thong_bao, (220, 225, 235), (man.get_width() // 2, man.get_height() // 2), giua=True)
    pygame.display.flip()
    pygame.event.pump()


def khoi_tao_mo_phong(seed, che_do="toi_uu"):
    """Mô phỏng mới, chạy khởi động 100 giây rồi xóa thống kê."""
    mp = MoPhong(seed=seed)
    mp.dat_che_do(che_do)
    mp.chay(100)
    mp.xoa_thong_ke()
    return mp


def chay_do_hoa(chup_anh=None, so_giay_chup=60, cam_thu=None, mo_do_thi=False):
    """Vòng lặp chính của cửa sổ pygame."""
    if pygame is None:
        print("Chưa cài pygame. Cài bằng:  pip install pygame")
        return
    if chup_anh:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    man = pygame.display.set_mode(CUA_SO_MAC_DINH, pygame.RESIZABLE)
    pygame.display.set_caption("Hệ thống giao thông 2x2 block (16 ngã tư) - Cấu trúc rời rạc")
    clock = pygame.time.Clock()
    fonts = (tao_font(17, True), tao_font(15, True), tao_font(13))
    f_to, f_tb, f_nho = fonts

    man_hinh_cho(man, f_to, "Đang dựng bản đồ khu dân cư ...")
    nen_muc = tao_nen_nhieu_muc(lambda co: tao_font(co, True))
    mm_w = 190
    mm_h = round(mm_w * CAO_M / RONG_M)

    man_hinh_cho(man, f_to, "Đang khởi động giao thông ...")
    mp = khoi_tao_mo_phong(seed=7)
    chon, toc_do, tam_dung, tich_luy = mp.ds_nut[0], 4, False, 0.0
    hien_thi_do_thi = mo_do_thi
    TOC_DO = [1, 2, 4, 8, 16]
    da_chup = False

    cam = Camera(man.get_width() - RONG_BANG, man.get_height())
    if cam_thu:                                   # chỉ dùng khi chụp ảnh thử
        cam.zoom = cam_thu[0]
        cam.tam_o(cam_thu[1], cam_thu[2])
    cache_nen = {}
    dang_keo, vi_tri_chuot_cu, dang_ban_do_nho = False, (0, 0), False
    phim_lia = {pygame.K_w: (0, 1), pygame.K_s: (0, -1), pygame.K_a: (1, 0), pygame.K_d: (-1, 0)}

    chay = True
    while chay:
        dt_that = min(clock.tick(60) / 1000.0, 0.1)
        man = pygame.display.get_surface()
        cam.dat_kich_thuoc(max(300, man.get_width() - RONG_BANG), man.get_height())

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                chay = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    chay = False
                elif ev.key == pygame.K_SPACE:
                    tam_dung = not tam_dung
                elif ev.key == pygame.K_m:
                    mp.dat_che_do("co_dinh" if mp.che_do == "toi_uu" else "toi_uu")
                elif ev.key == pygame.K_g:
                    hien_thi_do_thi = not hien_thi_do_thi
                elif ev.key == pygame.K_UP:
                    toc_do = TOC_DO[min(len(TOC_DO) - 1, TOC_DO.index(toc_do) + 1)]
                elif ev.key == pygame.K_DOWN:
                    toc_do = TOC_DO[max(0, TOC_DO.index(toc_do) - 1)]
                elif ev.key == pygame.K_r:
                    mp = khoi_tao_mo_phong(random.randint(1, 999), mp.che_do)
                    chon = mp.ds_nut[chon.stt - 1]
                elif ev.key == pygame.K_TAB:
                    buoc = -1 if ev.mod & pygame.KMOD_SHIFT else 1
                    chon = mp.ds_nut[(chon.stt - 1 + buoc) % len(mp.ds_nut)]
                elif pygame.K_1 <= ev.key <= pygame.K_4:      # chọn nút 1-4 trong block hiện tại
                    k4 = ev.key - pygame.K_1
                    r0, c0 = (chon.block // 2) * 2, (chon.block % 2) * 2
                    chon = mp.nut[r0 + k4 // 2][c0 + k4 % 2]
                elif ev.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    cam.zoom_tai(cam.vw / 2, cam.vh / 2, 1.15)
                elif ev.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    cam.zoom_tai(cam.vw / 2, cam.vh / 2, 1 / 1.15)
                elif ev.key in (pygame.K_0, pygame.K_KP0):
                    cam.dat_lai()

            elif ev.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if mx < cam.vw:
                    cam.zoom_tai(mx, my, 1.1 if ev.y > 0 else 1 / 1.1)

            elif ev.type == pygame.MOUSEBUTTONUP:
                if ev.button in (2, 3):
                    dang_keo = False
                elif ev.button == 1:
                    dang_ban_do_nho = False
            elif ev.type == pygame.MOUSEMOTION:
                if dang_keo:
                    cam.keo(ev.pos[0] - vi_tri_chuot_cu[0], ev.pos[1] - vi_tri_chuot_cu[1])
                    vi_tri_chuot_cu = ev.pos

        phim = pygame.key.get_pressed()               # lia camera bằng WASD (vẫn bị kẹp trong bản đồ)
        for kphim, (ddx, ddy) in phim_lia.items():
            if phim[kphim]:
                cam.keo(ddx * 420 * dt_that, ddy * 420 * dt_that)

        if not tam_dung:
            tich_luy += dt_that * toc_do
            n_buoc = 0
            while tich_luy >= DT and n_buoc < 40:     # giới hạn số bước để không bị đơ
                mp.buoc(DT)
                tich_luy -= DT
                n_buoc += 1
            tich_luy = min(tich_luy, 2 * DT)

        # ---- VẼ ----
        man.set_clip(pygame.Rect(0, 0, cam.vw, cam.vh))
        ve_nen_len_man_hinh(man, nen_muc, cam, cache_nen)
        for n in mp.ds_nut:
            ve_nut(man, mp, n, f_nho, f_tb, n is chon, cam)
        for xe in mp.xe:
            ve_xe(man, xe, cam)
        if hien_thi_do_thi:
            ve_do_thi_xung_dot(man, mp, chon, fonts, cam.vw, cam.vh, pygame.mouse.get_pos())
        man.set_clip(None)
        ve_bang(man, mp, fonts, chon, toc_do, tam_dung, cam)
        pygame.display.flip()

        if chup_anh and not da_chup and mp.t >= 100 + so_giay_chup:
            pygame.image.save(man, chup_anh)
            da_chup, chay = True, False
    pygame.quit()

# ==========================================================================
# PHẦN 10. ĐIỂM VÀO CHƯƠNG TRÌNH
# ==========================================================================

def in_ke_hoach_cac_nut():
    mp = MoPhong()
    print("KẾ HOẠCH ĐÈN TỪ CODE LÕI (2x2 block = 16 ngã tư, đủ 16 đèn)")
    ten = {(n.r, n.c): n.ten for n in mp.ds_nut}
    print("Đường nối bị bỏ:", ", ".join(f"{ten[a]}-{ten[b]}" for a, b in DUONG_BO))
    for n in mp.ds_nut:
        kh = n.kh["toi_uu"]
        print(f"  Nút {n.ten}: chu kỳ {kh.chu_ky}s | xanh {kh.xanh} | dừng {kh.dung}"
              + ("  (QUÁ TẢI)" if kh.qua_tai else ""))


if __name__ == "__main__":
    if "--so-sanh" in sys.argv:
        in_ke_hoach_cac_nut()
        so_sanh_khong_do_hoa()
    elif "--chup" in sys.argv:
        cam_thu = None
        if "--cam" in sys.argv:                  # --cam zoom,x_met,y_met
            z, wx, wy = (float(v) for v in sys.argv[sys.argv.index("--cam") + 1].split(","))
            cam_thu = (z, wx, wy)
        chay_do_hoa(chup_anh=sys.argv[sys.argv.index("--chup") + 1], cam_thu=cam_thu,
                    mo_do_thi="--do-thi" in sys.argv)
    else:
        in_ke_hoach_cac_nut()
        chay_do_hoa()