# -*- coding: utf-8 -*-
"""
PHẦN MỀM TỐI ƯU CHU KỲ ĐÈN GIAO THÔNG - Môn học: Cấu trúc Rời Rạc

Ý TƯỞNG
  BƯỚC 1. Mô hình hóa bằng đồ thị: mỗi "dòng xe" là một ĐỈNH; hai dòng xe đi cùng
          lúc sẽ va chạm nhau => nối bằng một CẠNH (đồ thị xung đột).
  BƯỚC 2. Tô màu đồ thị => chia pha: hai đỉnh kề nhau KHÔNG được cùng màu. Mỗi màu =
          một PHA đèn xanh; ít màu nhất (số sắc độ) = ít pha nhất = ít thời gian mất mát.
          Cài 2 thuật toán: Welsh-Powell (tham lam) và Quay lui (chính xác).
  BƯỚC 3. Tính chu kỳ tối ưu: công thức Webster, chia xanh theo lưu lượng,
          kiểm chứng bằng cách thử mọi chu kỳ và tính độ trễ trung bình.

Chạy:  python core.py
"""

# ==========================================================================
# PHẦN 0. DỮ LIỆU ĐẦU VÀO (bạn có thể sửa các số này)
# ==========================================================================

# Ngã tư 4 hướng B(ắc) N(am) D(ông) T(ây); mỗi hướng có 2 dòng xe: Th = đi thẳng,
# Re = rẽ trái (rẽ phải coi như đi tự do, không xét xung đột).
CAC_DONG_XE = [f"{h}_{k}" for h in "BNDT" for k in ("Th", "Re")]

TEN_HUONG = {"B": "Bắc", "N": "Nam", "D": "Đông", "T": "Tây"}
TEN_DAY_DU = {f"{h}_{k}": f"{ten} {kieu}" for h, ten in TEN_HUONG.items()
              for k, kieu in (("Th", "đi thẳng"), ("Re", "rẽ trái"))}

# Lưu lượng xe (xe/giờ) của từng dòng xe
LUU_LUONG = {"B_Th": 450, "B_Re": 100, "N_Th": 400, "N_Re": 90,
             "D_Th": 350, "D_Re": 80,  "T_Th": 330, "T_Re": 90}

# Lưu lượng bão hòa (xe/giờ xanh): số xe tối đa thông qua nếu đèn xanh liên tục.
# Xe đi thẳng thông thoáng hơn xe rẽ trái.
LUU_LUONG_BAO_HOA = {k: 1800 if k.endswith("Th") else 1500 for k in CAC_DONG_XE}

THOI_GIAN_MAT_MOI_PHA = 4          # giây mất mát mỗi pha (đèn vàng 3s + đỏ toàn phần 1s)
XANH_TOI_THIEU = 7                 # giây, đèn xanh mỗi pha tối thiểu (an toàn cho người đi bộ)
CHU_KY_MIN, CHU_KY_MAX = 30, 150   # giây, khoảng chu kỳ cho phép


# ==========================================================================
# PHẦN 1. XÂY DỰNG ĐỒ THỊ XUNG ĐỘT (danh sách kề: dict {đỉnh: tập đỉnh kề})
# ==========================================================================

def tao_do_thi_xung_dot():
    """
    Đồ thị xung đột của ngã tư (chỉ gồm các dòng xe có trong CAC_DONG_XE, nên ngã ba
    thiếu nhánh cũng dùng được). Hai dòng xe KHÔNG được đi cùng lúc nếu:
      (1) một dòng thuộc trục Bắc-Nam, dòng kia thuộc trục Đông-Tây (cắt ngang nhau);
      (2) cùng trục nhưng ngược chiều: xe rẽ trái cắt qua xe đi thẳng của hướng đối diện.
    """
    do_thi = {x: set() for x in CAC_DONG_XE}

    def them_canh(u, v):
        do_thi[u].add(v)
        do_thi[v].add(u)

    for u in do_thi:                                    # quy tắc (1)
        for v in do_thi:
            if (u[0] in "BN") != (v[0] in "BN"):
                them_canh(u, v)

    doi_dien = {"B": "N", "N": "B", "D": "T", "T": "D"}
    for huong, kia in doi_dien.items():                 # quy tắc (2)
        trai, thang = huong + "_Re", kia + "_Th"
        if trai in do_thi and thang in do_thi:          # thiếu nhánh thì thiếu dòng xe
            them_canh(trai, thang)
    return do_thi


# ==========================================================================
# PHẦN 2. TÔ MÀU ĐỒ THỊ (TỰ CÀI ĐẶT)
# ==========================================================================

def dinh_theo_bac_giam(do_thi):
    """Các đỉnh sắp theo bậc (số cạnh nối) giảm dần."""
    return sorted(do_thi, key=lambda d: len(do_thi[d]), reverse=True)


def to_mau_welsh_powell(do_thi):
    """
    THUẬT TOÁN 1: WELSH-POWELL (tham lam, nhanh nhưng không đảm bảo tối ưu).
      1. Sắp đỉnh theo bậc GIẢM DẦN.
      2. Với màu 0: duyệt danh sách, tô cho đỉnh chưa tô và KHÔNG kề đỉnh nào đã có màu 0.
      3. Chuyển sang màu 1, 2, ... đến khi tô hết.
    Trả về: dict {đỉnh: số màu}
    """
    thu_tu, mau, mau_hien_tai = dinh_theo_bac_giam(do_thi), {}, 0
    while len(mau) < len(do_thi):
        da_to = []                                      # các đỉnh được tô màu hiện tại
        for dinh in thu_tu:
            if dinh not in mau and not any(ke in da_to for ke in do_thi[dinh]):
                mau[dinh] = mau_hien_tai
                da_to.append(dinh)
        mau_hien_tai += 1
    return mau


def to_mau_quay_lui(do_thi):
    """
    THUẬT TOÁN 2: QUAY LUI - TÌM SỐ MÀU TỐI THIỂU CHÍNH XÁC.
    Thử k = 1, 2, 3, ... màu: gán màu lần lượt cho từng đỉnh, bế tắc thì "quay lui"
    đổi màu khác. k nhỏ nhất tô được chính là SỐ SẮC ĐỘ của đồ thị.
    """
    cac_dinh = dinh_theo_bac_giam(do_thi)               # bậc giảm dần => cắt nhánh sớm

    def thu_to_voi_k_mau(k):
        mau = {}

        def giai(vi_tri):
            if vi_tri == len(cac_dinh):
                return True
            dinh = cac_dinh[vi_tri]
            for c in range(k):
                if all(mau.get(ke) != c for ke in do_thi[dinh]):
                    mau[dinh] = c
                    if giai(vi_tri + 1):
                        return True
                    del mau[dinh]                       # QUAY LUI
            return False

        return mau if giai(0) else None

    for k in range(1, len(cac_dinh) + 1):
        ket_qua = thu_to_voi_k_mau(k)
        if ket_qua is not None:
            return ket_qua


def liet_ke_moi_cach_to_mau(do_thi, k):
    """
    Liệt kê (generator) TẤT CẢ cách tô đồ thị bằng đúng k màu. Mẹo phá đối xứng: đỉnh đầu
    luôn màu 0, mỗi đỉnh sau chỉ dùng màu <= (màu lớn nhất đã dùng + 1) => hai cách chỉ
    khác nhau do "đổi tên màu" không bị đếm trùng.
    """
    cac_dinh, mau = dinh_theo_bac_giam(do_thi), {}

    def giai(vi_tri, mau_lon_nhat):
        if vi_tri == len(cac_dinh):
            if mau_lon_nhat == k - 1:                   # phải dùng đủ k màu
                yield dict(mau)
            return
        dinh = cac_dinh[vi_tri]
        for c in range(min(k, mau_lon_nhat + 2)):
            if all(mau.get(ke) != c for ke in do_thi[dinh]):
                mau[dinh] = c
                yield from giai(vi_tri + 1, max(mau_lon_nhat, c))
                del mau[dinh]                           # quay lui

    yield from giai(0, -1)


def chon_cach_chia_pha_tot_nhat(do_thi):
    """
    Nhiều cách tô màu cùng dùng số màu tối thiểu k, nhưng không phải cách nào cũng tốt
    (vd ghép "Bắc thẳng + Bắc rẽ trái" vào 1 pha vẫn hợp lệ nhưng lãng phí).
    => Với mỗi cách tính Y (tổng y tới hạn các pha), chọn cách có Y NHỎ NHẤT
       (Y nhỏ => chu kỳ ngắn => xe đỡ chờ).  Trả về: (danh sách pha, Y)
    """
    k = max(to_mau_quay_lui(do_thi).values()) + 1       # số sắc độ
    tot_nhat, y_min = None, float("inf")
    for mau in liet_ke_moi_cach_to_mau(do_thi, k):
        cac_pha = chia_pha_tu_mau(mau)
        y = sum(tinh_y_toi_han_moi_pha(cac_pha))
        if y < y_min:
            tot_nhat, y_min = cac_pha, y
    return tot_nhat, y_min


def kiem_tra_to_mau_hop_le(do_thi, mau):
    """Không có cạnh nào nối 2 đỉnh cùng màu."""
    return all(mau[u] != mau[v] for u in do_thi for v in do_thi[u])


def chia_pha_tu_mau(mau):
    """Đổi kết quả tô màu thành danh sách PHA. Vd {A:0, B:0, C:1} -> [[A, B], [C]]."""
    cac_pha = [[] for _ in range(max(mau.values()) + 1)]
    for dinh in CAC_DONG_XE:                            # thứ tự cố định cho dễ đọc
        cac_pha[mau[dinh]].append(dinh)
    return cac_pha


# ==========================================================================
# PHẦN 3. TÍNH CHU KỲ ĐÈN TỐI ƯU (WEBSTER)
# ==========================================================================

def ty_so_luu_luong(dong_xe):
    """y = q / s: dòng xe đó "chiếm" bao nhiêu phần thời gian xanh."""
    return LUU_LUONG[dong_xe] / LUU_LUONG_BAO_HOA[dong_xe]


def tinh_y_toi_han_moi_pha(cac_pha):
    """Thời gian xanh của pha phải đủ cho dòng ĐÔNG NHẤT (dòng tới hạn): y_pha = max y."""
    return [max(ty_so_luu_luong(x) for x in pha) for pha in cac_pha]


def chu_ky_webster(tong_mat_mat, Y):
    """
    CÔNG THỨC WEBSTER:  C0 = (1.5 * L + 5) / (1 - Y)
      L: tổng thời gian mất mát trong 1 chu kỳ (giây);  Y: tổng y tới hạn của mọi pha.
    Y >= 1 thì ngã tư quá tải (không chu kỳ nào đủ) => None.
    """
    return None if Y >= 1 else (1.5 * tong_mat_mat + 5) / (1 - Y)


def chia_thoi_gian_xanh(y_pha, chu_ky, tong_mat_mat):
    """
    Chia xanh hiệu dụng cho từng pha TỈ LỆ THUẬN với y_pha: g_i = (y_i / Y) * (C - L),
    nhưng mỗi pha luôn được ít nhất XANH_TOI_THIEU giây ("chia tràn nước"):
      1. Chia theo tỉ lệ cho các pha chưa bị ghim.
      2. Pha nào được ít hơn mức tối thiểu thì GHIM = tối thiểu, chia lại phần dư cho pha còn lại.
      3. Làm tròn số nguyên theo phần dư lớn nhất để tổng các pha khớp chính xác C - L.
    """
    n, tong_xanh = len(y_pha), chu_ky - tong_mat_mat
    ghim, chia = {}, {}
    while True:
        con_lai = [i for i in range(n) if i not in ghim]
        if not con_lai:
            break
        quy = tong_xanh - XANH_TOI_THIEU * len(ghim)
        Y = sum(y_pha[i] for i in con_lai)
        chia = {i: (y_pha[i] / Y if Y > 0 else 1 / len(con_lai)) * quy for i in con_lai}
        moi_ghim = [i for i in con_lai if chia[i] < XANH_TOI_THIEU]
        if not moi_ghim:
            break
        ghim.update({i: XANH_TOI_THIEU for i in moi_ghim})
    xanh_thuc = [ghim[i] if i in ghim else chia[i] for i in range(n)]

    xanh = [int(g) for g in xanh_thuc]
    du = tong_xanh - sum(xanh)
    for i in sorted(range(n), key=lambda i: xanh_thuc[i] - xanh[i], reverse=True)[:max(0, du)]:
        xanh[i] += 1
    return xanh


# ==========================================================================
# PHẦN 4. ĐÁNH GIÁ: ĐỘ TRỄ TRUNG BÌNH (công thức Webster)
# ==========================================================================

def do_tre_mot_dong_xe(q_gio, s_gio, xanh, chu_ky):
    """
    Độ trễ trung bình của 1 xe (giây) theo Webster:
        d = C(1-λ)² / (2(1-λx))  +  x² / (2q(1-x))  -  0.65 (C/q²)^(1/3) x^(2+5λ)
      q, s: lưu lượng / lưu lượng bão hòa (xe/giây);  λ = g/C: tỉ lệ xanh;  x = q/(λ·s): độ bão hòa
    x >= 1: hàng xe tăng mãi -> vô cùng.
    """
    q, s = q_gio / 3600, s_gio / 3600
    lam = xanh / chu_ky
    if lam <= 0:
        return float("inf")
    x = q / (lam * s)
    if x >= 1:
        return float("inf")
    return (chu_ky * (1 - lam) ** 2 / (2 * (1 - lam * x))
            + x ** 2 / (2 * q * (1 - x))
            - 0.65 * (chu_ky / q ** 2) ** (1 / 3) * x ** (2 + 5 * lam))


def do_tre_trung_binh_nga_tu(cac_pha, xanh_pha, chu_ky):
    """Độ trễ TB của mọi xe qua ngã tư (giây/xe) = Σ q_i·d_i / Σ q_i (trọng số theo lưu lượng)."""
    tong_tre = tong_q = 0.0
    for pha, xanh in zip(cac_pha, xanh_pha):
        for dong_xe in pha:
            d = do_tre_mot_dong_xe(LUU_LUONG[dong_xe], LUU_LUONG_BAO_HOA[dong_xe], xanh, chu_ky)
            if d == float("inf"):
                return d
            tong_tre += LUU_LUONG[dong_xe] * d
            tong_q += LUU_LUONG[dong_xe]
    return tong_tre / tong_q


def tim_chu_ky_bang_vet_can(cac_pha, y_pha, tong_mat_mat):
    """
    KIỂM CHỨNG bằng vét cạn: thử TỪNG chu kỳ từ CHU_KY_MIN đến CHU_KY_MAX, tính độ trễ
    trung bình rồi chọn chu kỳ NHỎ NHẤT. Trả về ((chu kỳ, xanh, độ trễ), bảng [(C, d)]).
    """
    tot_nhat, bang = (None, None, float("inf")), []
    for C in range(CHU_KY_MIN, CHU_KY_MAX + 1):
        if C - tong_mat_mat < XANH_TOI_THIEU * len(cac_pha):    # quá ngắn, thiếu xanh tối thiểu
            continue
        xanh = chia_thoi_gian_xanh(y_pha, C, tong_mat_mat)
        d = do_tre_trung_binh_nga_tu(cac_pha, xanh, C)
        bang.append((C, d))
        if d < tot_nhat[2]:
            tot_nhat = (C, xanh, d)
    return tot_nhat, bang


# ==========================================================================
# PHẦN 5. HIỂN THỊ KẾT QUẢ
# ==========================================================================

def in_tieu_de(noi_dung):
    print("\n" + "=" * 70 + "\n " + noi_dung + "\n" + "=" * 70)


def in_do_thi(do_thi):
    for dinh in CAC_DONG_XE:
        print(f"  {dinh} ({TEN_DAY_DU[dinh]:<14}) xung đột với: {', '.join(sorted(do_thi[dinh]))}")


def in_cac_pha(cac_pha, xanh_pha=None, y_pha=None):
    for i, pha in enumerate(cac_pha):
        thong_tin = (f" | y={y_pha[i]:.3f}" if y_pha is not None else "") \
                    + (f" | xanh={xanh_pha[i]}s" if xanh_pha is not None else "")
        print(f"  Pha {i + 1}: {', '.join(TEN_DAY_DU[x] for x in pha)}{thong_tin}")


def ve_dong_ho_chu_ky(xanh_pha, chu_ky):
    """Vẽ chu kỳ đèn bằng ký tự (1 ký tự ~ 1 giây): X = xanh, . = mất mát."""
    mat = THOI_GIAN_MAT_MOI_PHA
    print("\n  Sơ đồ chu kỳ (1 ký tự ~ 1 giây, X = xanh, . = mất mát):")
    for i, g in enumerate(xanh_pha):
        truoc = sum(xanh_pha[:i]) + mat * i
        print(f"  Pha {i + 1}: |{' ' * truoc}{'X' * g}{'.' * mat}")
    print(f"  Tổng chu kỳ = {chu_ky} giây")


def ve_bieu_do_do_tre(bang, chu_ky_chon):
    """Biểu đồ cột ngang: độ trễ trung bình theo chu kỳ (mỗi 10 giây)."""
    print("\n  Độ trễ trung bình (giây/xe) theo chu kỳ:")
    for C, d in bang:
        if C % 10:
            continue
        if d == float("inf"):
            print(f"  C={C:>3}s | quá tải")
        else:
            danh_dau = " <-- gần tối ưu" if abs(C - chu_ky_chon) < 5 else ""
            print(f"  C={C:>3}s | {'#' * int(d / 2)} {d:.1f}{danh_dau}")


# ==========================================================================
# PHẦN 6. CHƯƠNG TRÌNH CHÍNH
# ==========================================================================

def main():
    # ---- Bước 1: đồ thị xung đột ----
    in_tieu_de("BƯỚC 1: ĐỒ THỊ XUNG ĐỘT")
    do_thi = tao_do_thi_xung_dot()
    in_do_thi(do_thi)

    # ---- Bước 2: tô màu, chia pha ----
    in_tieu_de("BƯỚC 2: TÔ MÀU ĐỒ THỊ -> CHIA PHA")
    for ten, mau in (("Welsh-Powell ", to_mau_welsh_powell(do_thi)),
                     ("Quay lui     ", to_mau_quay_lui(do_thi))):
        print(f"  {ten}: {max(mau.values()) + 1} màu (hợp lệ: {kiem_tra_to_mau_hop_le(do_thi, mau)})")

    cac_pha, _ = chon_cach_chia_pha_tot_nhat(do_thi)    # cách tô màu tối thiểu cho Y nhỏ nhất
    print(f"\n  => Số sắc độ = {len(cac_pha)} => ngã tư cần {len(cac_pha)} pha")
    print("  (đã chọn cách ghép pha cho Y nhỏ nhất trong mọi cách tô màu):")
    in_cac_pha(cac_pha)

    # ---- Bước 3: chu kỳ Webster ----
    in_tieu_de("BƯỚC 3: CHU KỲ TỐI ƯU (WEBSTER)")
    y_pha = tinh_y_toi_han_moi_pha(cac_pha)
    Y, L = sum(y_pha), THOI_GIAN_MAT_MOI_PHA * len(cac_pha)
    print(f"  y tới hạn từng pha = {[round(y, 3) for y in y_pha]}")
    print(f"  Y = tổng y         = {Y:.3f}")
    print(f"  L = tổng mất mát   = {L} giây")

    C0 = chu_ky_webster(L, Y)
    if C0 is None:
        print("  !! Y >= 1: ngã tư QUÁ TẢI, không có chu kỳ nào đáp ứng được.")
        print("     Hãy giảm lưu lượng hoặc tăng số làn (tăng lưu lượng bão hòa).")
        return

    C = int(round(min(max(C0, CHU_KY_MIN), CHU_KY_MAX)))    # giới hạn trong khoảng thực tế
    print(f"  C0 (Webster)       = {C0:.1f} giây  -> chọn C = {C} giây")
    xanh_pha = chia_thoi_gian_xanh(y_pha, C, L)
    print("\n  Kế hoạch đèn:")
    in_cac_pha(cac_pha, xanh_pha, y_pha)
    ve_dong_ho_chu_ky(xanh_pha, C)

    # ---- Bước 4: kiểm chứng bằng vét cạn ----
    in_tieu_de("BƯỚC 4: KIỂM CHỨNG BẰNG VÉT CẠN")
    d_webster = do_tre_trung_binh_nga_tu(cac_pha, xanh_pha, C)
    (C_tot, xanh_tot, d_tot), bang = tim_chu_ky_bang_vet_can(cac_pha, y_pha, L)
    print(f"  Webster : C = {C:>3}s, độ trễ TB = {d_webster:.2f} giây/xe")
    print(f"  Vét cạn : C = {C_tot:>3}s, độ trễ TB = {d_tot:.2f} giây/xe, xanh = {xanh_tot}")
    ve_bieu_do_do_tre(bang, C)

    # ---- So sánh với phương án cố định ----
    in_tieu_de("SO SÁNH VỚI ĐÈN CHU KỲ CỐ ĐỊNH 60s (chia đều)")
    xanh_deu = [(60 - L) // len(cac_pha)] * len(cac_pha)
    d_deu = do_tre_trung_binh_nga_tu(cac_pha, xanh_deu, 60)
    qua_tai = d_deu == float("inf")
    print(f"  Chia đều, C=60s : độ trễ TB = {'quá tải' if qua_tai else f'{d_deu:.2f} giây/xe'}")
    print(f"  Tối ưu Webster  : độ trễ TB = {d_webster:.2f} giây/xe")
    if not qua_tai:
        print(f"  => Giảm được {(d_deu - d_webster) / d_deu * 100:.1f}% độ trễ.")


if __name__ == "__main__":
    main()