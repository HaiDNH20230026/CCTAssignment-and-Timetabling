# -*- coding: utf-8 -*-
"""
common.py - Phần dùng chung cho mọi solver
==========================================
Bài toán: Class - Course - Teacher Assignment and TimeTabling (đề tài số 8).

File này làm 4 việc:
  1. Đọc input đúng định dạng đề bài                  -> read_instance()
  2. Tiền xử lý: tạo danh sách LỚP-MÔN, tập kíp bắt đầu hợp lệ U_c,
     tập giáo viên dạy được T_c, các cặp xung đột Q_lop / Q_gv
  3. Thuật toán tham lam (greedy) làm lời giải khởi tạo / warm-start
  4. Kiểm tra và ghi output đúng định dạng đề bài     -> verify(), write_solution()

Ký hiệu (trùng với file modeling):
  T, N, M          : số giáo viên, số lớp, số môn
  R[i]             : danh sách môn lớp i phải học         (i = 1..N)
  A[t]             : danh sách môn giáo viên t dạy được   (t = 1..T)
  d[m]             : số tiết của môn m                    (m = 1..M)
  L                : số lớp-môn, chỉ số c = 0..L-1
  cls[c], sub[c]   : lớp và môn của lớp-môn c
  dur[c]           : = d[sub[c]]  (ký hiệu d_c trong modeling)
  TC[c]            : tập giáo viên dạy được lớp-môn c     (T_c)
  UC[c]            : tập kíp bắt đầu hợp lệ của c          (U_c)
  Kíp s            : 1..60.  ngày = (s-1)//12, buổi = (s-1)//6, tiết trong buổi = (s-1)%6 + 1

Các mảng của lớp / môn / giáo viên / kíp đánh chỉ số từ 1 (phần tử 0 bỏ trống)
để khớp với ký hiệu của đề bài.

Lưu ý: chuỗi in ra màn hình để KHÔNG dấu, tránh lỗi encoding trên console Windows.
"""

import sys
import time
import argparse

# ---------------------------------------------------------------------------
# Hằng số khung thời gian
# ---------------------------------------------------------------------------
NUM_DAYS = 5                 # 5 ngày học
SESSIONS_PER_DAY = 2         # sáng + chiều
PERIODS_PER_SESSION = 6      # 6 tiết / buổi
NUM_SLOTS = NUM_DAYS * SESSIONS_PER_DAY * PERIODS_PER_SESSION   # = 60 kíp

# Quy tắc kíp bắt đầu hợp lệ (xem mục "Giả thiết" trong file modeling):
#   "session": lớp-môn phải nằm trọn trong 1 buổi (6 tiết)   <- mặc định, khớp ví dụ đề bài
#   "day"    : nằm trọn trong 1 ngày (12 tiết, được vắt qua trưa)
#   "week"   : chỉ cần nằm trong 60 kíp của tuần
BLOCK_LENGTH = {"session": 6, "day": 12, "week": 60}


# ---------------------------------------------------------------------------
# Cấu trúc dữ liệu của 1 instance
# ---------------------------------------------------------------------------
class Instance:
    def __init__(self):
        self.T = 0
        self.N = 0
        self.M = 0
        self.R = []          # R[i] : list môn của lớp i
        self.A = []          # A[t] : list môn giáo viên t dạy được
        self.d = []          # d[m] : số tiết môn m
        self.rule = "session"
        # --- dữ liệu sau tiền xử lý ---
        self.L = 0
        self.cls = []        # cls[c]
        self.sub = []        # sub[c]
        self.dur = []        # dur[c]
        self.TC = []         # TC[c] : list giáo viên
        self.UC = []         # UC[c] : list kíp bắt đầu hợp lệ
        self.lm_of_class = []    # lm_of_class[i]  : list lớp-môn của lớp i
        self.lm_of_teacher = []  # lm_of_teacher[t]: list lớp-môn mà t CÓ THỂ dạy

    def schedulable(self, c):
        """Lớp-môn c có ít nhất 1 giáo viên và 1 kíp hợp lệ hay không."""
        return len(self.TC[c]) > 0 and len(self.UC[c]) > 0

    def num_schedulable(self):
        cnt = 0
        for c in range(self.L):
            if self.schedulable(c):
                cnt += 1
        return cnt


def valid_starts(duration, rule):
    """
    Tập kíp bắt đầu hợp lệ U(d) cho lớp-môn có 'duration' tiết.
    Với độ dài khối P (6 / 12 / 60):
        u hợp lệ  <=>  ((u-1) mod P) + d <= P
    tức là đoạn [u, u+d-1] nằm trọn trong một khối P tiết liên tiếp.
    """
    P = BLOCK_LENGTH[rule]
    result = []
    for u in range(1, NUM_SLOTS + 1):
        pos = (u - 1) % P             # vị trí của u trong khối (0..P-1)
        if pos + duration <= P:
            result.append(u)
    return result


def read_tokens(path):
    """Đọc toàn bộ file thành mảng số nguyên (bỏ qua xuống dòng)."""
    if path == "-":
        text = sys.stdin.read()
    else:
        f = open(path, "r", encoding="utf-8")
        text = f.read()
        f.close()
    parts = text.split()
    tokens = []
    for p in parts:
        tokens.append(int(p))
    return tokens


def read_instance(path, rule="session"):
    """
    Đọc input:
      Dòng 1       : T N M
      N dòng tiếp  : danh sách môn của lớp i, kết thúc bằng 0
      T dòng tiếp  : danh sách môn giáo viên t dạy được, kết thúc bằng 0
      Dòng cuối    : d(1) .. d(M)
    Đọc theo luồng token nên không phụ thuộc cách xuống dòng.
    """
    tok = read_tokens(path)
    pos = 0
    inst = Instance()
    inst.rule = rule
    inst.T = tok[pos]; pos += 1
    inst.N = tok[pos]; pos += 1
    inst.M = tok[pos]; pos += 1

    # ---- Bước 1: danh sách môn của từng lớp (bỏ trùng lặp nếu có) ----
    inst.R = [[]]                       # R[0] bỏ trống
    for i in range(1, inst.N + 1):
        lst = []
        seen = [False] * (inst.M + 1)
        while True:
            m = tok[pos]; pos += 1
            if m == 0:
                break
            if 1 <= m <= inst.M and not seen[m]:
                seen[m] = True
                lst.append(m)
        inst.R.append(lst)

    # ---- Bước 2: danh sách môn của từng giáo viên ----
    inst.A = [[]]
    for t in range(1, inst.T + 1):
        lst = []
        seen = [False] * (inst.M + 1)
        while True:
            m = tok[pos]; pos += 1
            if m == 0:
                break
            if 1 <= m <= inst.M and not seen[m]:
                seen[m] = True
                lst.append(m)
        inst.A.append(lst)

    # ---- Bước 3: số tiết của từng môn ----
    inst.d = [0] * (inst.M + 1)
    for m in range(1, inst.M + 1):
        inst.d[m] = tok[pos]; pos += 1

    preprocess(inst)
    return inst


def preprocess(inst):
    """Tạo danh sách lớp-môn và các tập T_c, U_c."""
    # ---- teachers_of_subject[m] = list giáo viên dạy được môn m ----
    teachers_of_subject = []
    for m in range(inst.M + 1):
        teachers_of_subject.append([])
    for t in range(1, inst.T + 1):
        for m in inst.A[t]:
            teachers_of_subject[m].append(t)

    # ---- U(d) tính 1 lần cho mỗi độ dài khác nhau ----
    starts_cache = {}

    inst.cls = []
    inst.sub = []
    inst.dur = []
    inst.TC = []
    inst.UC = []
    inst.lm_of_class = []
    for i in range(inst.N + 1):
        inst.lm_of_class.append([])
    inst.lm_of_teacher = []
    for t in range(inst.T + 1):
        inst.lm_of_teacher.append([])

    c = 0
    for i in range(1, inst.N + 1):
        for m in inst.R[i]:
            dm = inst.d[m]
            if dm not in starts_cache:
                starts_cache[dm] = valid_starts(dm, inst.rule)
            inst.cls.append(i)
            inst.sub.append(m)
            inst.dur.append(dm)
            inst.TC.append(teachers_of_subject[m])
            inst.UC.append(starts_cache[dm])
            inst.lm_of_class[i].append(c)
            for t in teachers_of_subject[m]:
                inst.lm_of_teacher[t].append(c)
            c += 1
    inst.L = c


def class_conflict_pairs(inst):
    """
    Q_lop = { (c1, c2) : c1 < c2, cls[c1] == cls[c2] }
    (hai lớp-môn cùng lớp luôn không được chồng lấp)
    Chỉ lấy lớp-môn xếp được (có giáo viên và có kíp hợp lệ).
    """
    pairs = []
    for i in range(1, inst.N + 1):
        lst = inst.lm_of_class[i]
        for a in range(len(lst)):
            if not inst.schedulable(lst[a]):
                continue
            for b in range(a + 1, len(lst)):
                if not inst.schedulable(lst[b]):
                    continue
                pairs.append((lst[a], lst[b]))
    return pairs


def teacher_conflict_pairs(inst):
    """
    Q_gv = { (c1, c2) : c1 < c2, cls[c1] != cls[c2], T_c1 ∩ T_c2 ≠ ∅ }
    Trả về list (c1, c2, common) với common = T_c1 ∩ T_c2.
    Cặp cùng lớp đã bị Q_lop chi phối (luôn phải rời nhau) nên không đưa vào đây.
    """
    pairs = []
    for c1 in range(inst.L):
        if not inst.schedulable(c1):
            continue
        mark = [False] * (inst.T + 1)
        for t in inst.TC[c1]:
            mark[t] = True
        for c2 in range(c1 + 1, inst.L):
            if inst.cls[c1] == inst.cls[c2] or not inst.schedulable(c2):
                continue
            common = []
            for t in inst.TC[c2]:
                if mark[t]:
                    common.append(t)
            if len(common) > 0:
                pairs.append((c1, c2, common))
    return pairs


# ---------------------------------------------------------------------------
# Thuật toán tham lam (warm-start / cận dưới / sửa chữa sau rounding)
# ---------------------------------------------------------------------------
def greedy(inst, fixed=None):
    """
    Xếp lần lượt từng lớp-môn vào (kíp, giáo viên) đầu tiên còn trống.
    Thứ tự: lớp-môn "khó" trước (ít giáo viên hơn, nhiều tiết hơn).
    'fixed' : list (c, u, t) đã xếp trước (vd. từ LP rounding) - giữ nguyên.
    Trả về list (c, u, t).
    """
    # busy_class[i][s] = True nếu lớp i bận ở kíp s
    busy_class = []
    for i in range(inst.N + 1):
        busy_class.append([False] * (NUM_SLOTS + 2))
    busy_teacher = []
    for t in range(inst.T + 1):
        busy_teacher.append([False] * (NUM_SLOTS + 2))
    load = [0] * (inst.T + 1)          # tổng số tiết đã giao cho giáo viên t
    done = [False] * inst.L
    result = []

    # ---- Bước 1: đặt các lớp-môn đã cố định ----
    if fixed is not None:
        for (c, u, t) in fixed:
            done[c] = True
            result.append((c, u, t))
            for s in range(u, u + inst.dur[c]):
                busy_class[inst.cls[c]][s] = True
                busy_teacher[t][s] = True
            load[t] += inst.dur[c]

    # ---- Bước 2: sắp thứ tự các lớp-môn còn lại ----
    order = []
    for c in range(inst.L):
        if not done[c] and inst.schedulable(c):
            order.append((len(inst.TC[c]), -inst.dur[c], c))
    order.sort()

    # ---- Bước 3: với mỗi lớp-môn, thử từng kíp x từng giáo viên (ít tải trước) ----
    for item in order:
        c = item[2]
        i = inst.cls[c]
        dc = inst.dur[c]
        teachers = []
        for t in inst.TC[c]:
            teachers.append((load[t], t))
        teachers.sort()
        placed = False
        for u in inst.UC[c]:
            # lớp i có trống trong [u, u+dc-1] không?
            ok = True
            for s in range(u, u + dc):
                if busy_class[i][s]:
                    ok = False
                    break
            if not ok:
                continue
            for pair in teachers:
                t = pair[1]
                free = True
                for s in range(u, u + dc):
                    if busy_teacher[t][s]:
                        free = False
                        break
                if free:
                    for s in range(u, u + dc):
                        busy_class[i][s] = True
                        busy_teacher[t][s] = True
                    load[t] += dc
                    result.append((c, u, t))
                    placed = True
                    break
            if placed:
                break
    return result


# ---------------------------------------------------------------------------
# Kiểm tra lời giải (dùng chung cho mọi solver và checker.py)
# ---------------------------------------------------------------------------
def verify(inst, assign):
    """assign: list (c, u, t). Trả về list thông báo lỗi (rỗng = hợp lệ)."""
    errors = []
    busy_class = []
    for i in range(inst.N + 1):
        busy_class.append([0] * (NUM_SLOTS + 2))
    busy_teacher = []
    for t in range(inst.T + 1):
        busy_teacher.append([0] * (NUM_SLOTS + 2))
    used = [False] * inst.L
    for (c, u, t) in assign:
        if used[c]:
            errors.append("lop-mon %d-%d bi xep 2 lan" % (inst.cls[c], inst.sub[c]))
        used[c] = True
        if t not in inst.TC[c]:
            errors.append("giao vien %d khong day duoc mon %d" % (t, inst.sub[c]))
        if u not in inst.UC[c]:
            errors.append("kip %d khong hop le cho lop-mon %d-%d (d=%d)"
                          % (u, inst.cls[c], inst.sub[c], inst.dur[c]))
            continue
        for s in range(u, u + inst.dur[c]):
            busy_class[inst.cls[c]][s] += 1
            if 1 <= t <= inst.T:
                busy_teacher[t][s] += 1
    for i in range(1, inst.N + 1):
        for s in range(1, NUM_SLOTS + 1):
            if busy_class[i][s] > 1:
                errors.append("lop %d bi chong lap o kip %d" % (i, s))
    for t in range(1, inst.T + 1):
        for s in range(1, NUM_SLOTS + 1):
            if busy_teacher[t][s] > 1:
                errors.append("giao vien %d bi chong lap o kip %d" % (t, s))
    return errors


# ---------------------------------------------------------------------------
# Ghi output và tiện ích dòng lệnh
# ---------------------------------------------------------------------------
def format_solution(inst, assign):
    """Output: dòng 1 = K; mỗi dòng sau: x y u v (lớp, môn, kíp bắt đầu, giáo viên)."""
    rows = []
    for (c, u, t) in assign:
        rows.append((inst.cls[c], inst.sub[c], u, t))
    rows.sort()
    lines = [str(len(rows))]
    for r in rows:
        lines.append("%d %d %d %d" % (r[0], r[1], r[2], r[3]))
    return "\n".join(lines) + "\n"


def write_solution(inst, assign, out_path=None):
    text = format_solution(inst, assign)
    if out_path is None:
        sys.stdout.write(text)
    else:
        f = open(out_path, "w", encoding="utf-8")
        f.write(text)
        f.close()


def log(msg):
    """Thông tin phụ in ra stderr để stdout chỉ chứa đúng output."""
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def make_arg_parser(description, default_time=30.0):
    p = argparse.ArgumentParser(description=description)
    p.add_argument("input", help="file input (dung '-' de doc stdin)")
    p.add_argument("-o", "--output", default=None, help="file output (mac dinh: stdout)")
    p.add_argument("-t", "--time", type=float, default=default_time,
                   help="gioi han thoi gian (giay)")
    p.add_argument("--rule", default="session", choices=["session", "day", "week"],
                   help="quy tac kip hop le (mac dinh: session = nam tron trong 1 buoi)")
    p.add_argument("-q", "--quiet", action="store_true", help="khong in log")
    return p


def run_main(solve_fn, name, default_time=30.0, extra_args=None):
    """
    Khung main() chung: đọc input -> gọi solve_fn -> kiểm tra -> ghi output.
    solve_fn(inst, time_limit, args) trả về (assign, info) với
      assign = list (c, u, t),  info = dict(status=..., bound=...)
    """
    parser = make_arg_parser(name, default_time)
    if extra_args is not None:
        extra_args(parser)
    args = parser.parse_args()
    inst = read_instance(args.input, args.rule)
    t0 = time.time()
    assign, info = solve_fn(inst, args.time, args)
    elapsed = time.time() - t0
    errors = verify(inst, assign)
    if not args.quiet:
        log("[%s] L=%d (xep duoc toi da %d), K=%d, status=%s, bound=%s, time=%.2fs"
            % (name, inst.L, inst.num_schedulable(), len(assign),
               info.get("status", "?"), str(info.get("bound", "?")), elapsed))
        if len(errors) > 0:
            log("  !! LOI GIAI KHONG HOP LE:")
            for e in errors[:10]:
                log("     " + e)
    write_solution(inst, assign, args.output)


