# -*- coding: utf-8 -*-
"""
s6_lp_relaxation.py - LINEAR PROGRAMMING: nới lỏng LP + làm tròn (rounding) / lặn (diving)
=========================================================================================
Lấy mô hình time-indexed của s4 nhưng cho biến LIÊN TỤC 0 <= x[c,t,u] <= 1 rồi giải bằng
GLOP (simplex của OR-Tools). LP ở dạng chuẩn của slide: f(x) = cx -> max, Ax <= b, x >= 0
với c = (1,...,1), A là ma trận 0/1 của ràng buộc (1)-(3), b = (1,...,1). Từ lời giải LP:

  1. CẬN TRÊN:  K* <= floor(z_LP)   (vì bài toán max, nới lỏng LP cho cận trên;
                 mục tiêu nguyên nên lấy phần nguyên)
  2. LỜI GIẢI NGUYÊN bằng một trong hai heuristic:
     --mode round : sắp biến theo giá trị LP giảm dần, nhận biến nếu không xung đột
                    (randomized/greedy rounding), rồi greedy lấp chỗ trống.
     --mode dive  : (mặc định) "LP diving": lặp
                       giải LP -> cố định (lb = 1) mọi biến ≈ 1 và biến phân số lớn nhất
                    cho đến khi lời giải LP nguyên. Mỗi lần giải lại dùng warm-start
                    của simplex đối ngẫu nên nhanh.
  3. ĐỐI NGẪU (mở rộng, ngoài nội dung slide; bật bằng --duals): giá trị đối ngẫu (shadow price) của ràng buộc giáo viên-kíp / lớp-kíp cho biết
     "nếu giáo viên t có thêm 1 đơn vị năng lực ở kíp s thì mục tiêu LP tăng bao nhiêu"
     -> chỉ ra giáo viên / lớp là "nút cổ chai".

Cách chạy:
    python s6_lp_relaxation.py tests/example.txt [--mode dive|round] [--duals]
"""

from ortools.linear_solver import pywraplp
from common import run_main, greedy, log, NUM_SLOTS
from s4_mip_time_indexed import build_time_indexed

NAME = "LP relaxation"
EPS = 1e-6


def add_args(parser):
    parser.add_argument("--mode", default="dive", choices=["dive", "round"])
    parser.add_argument("--duals", action="store_true", help="in phan tich doi ngau (nut co chai)")


def print_duals(inst, M):
    """Tổng giá trị đối ngẫu theo từng giáo viên / lớp (ràng buộc (3), (2))."""
    rows = []
    for t in range(1, inst.T + 1):
        total = 0.0
        for s in range(1, NUM_SLOTS + 1):
            con = M["cons_teacher"][t][s]
            if con is not None:
                total += abs(con.dual_value())
        rows.append((-total, "giao vien", t))
    for i in range(1, inst.N + 1):
        total = 0.0
        for s in range(1, NUM_SLOTS + 1):
            con = M["cons_class"][i][s]
            if con is not None:
                total += abs(con.dual_value())
        rows.append((-total, "lop", i))
    rows.sort()
    log("  Phan tich doi ngau - top 'nut co chai' (tong shadow price):")
    for k in range(min(5, len(rows))):
        if -rows[k][0] > EPS:
            log("     %-9s %3d : %.3f" % (rows[k][1], rows[k][2], -rows[k][0]))


def round_solution(inst, M):
    """Làm tròn tham lam: nhận biến theo giá trị LP giảm dần nếu không xung đột."""
    xs = M["xs"]
    cand = []
    for k in range(len(xs)):
        val = xs[k].solution_value()
        if val > EPS:
            cand.append((-val, k))
    cand.sort()
    busy_class = []
    for i in range(inst.N + 1):
        busy_class.append([False] * (NUM_SLOTS + 2))
    busy_teacher = []
    for t in range(inst.T + 1):
        busy_teacher.append([False] * (NUM_SLOTS + 2))
    done = [False] * inst.L
    chosen = []
    for item in cand:
        k = item[1]
        c = M["var_c"][k]
        t = M["var_t"][k]
        u = M["var_u"][k]
        i = inst.cls[c]
        if done[c]:
            continue
        ok = True
        for s in range(u, u + inst.dur[c]):
            if busy_class[i][s] or busy_teacher[t][s]:
                ok = False
                break
        if not ok:
            continue
        done[c] = True
        for s in range(u, u + inst.dur[c]):
            busy_class[i][s] = True
            busy_teacher[t][s] = True
        chosen.append((c, u, t))
    return chosen


def solve(inst, time_limit, args):
    solver = pywraplp.Solver.CreateSolver("GLOP")
    M = build_time_indexed(inst, solver, integer=False)
    xs = M["xs"]
    if len(xs) == 0:
        return [], {"status": "OPTIMAL", "bound": 0}
    log("  LP: so bien = %d, so rang buoc = %d" % (solver.NumVariables(), solver.NumConstraints()))

    # ------------------------------------------------------------------
    # Bước 1: giải nới lỏng LP lần đầu -> cận trên
    # ------------------------------------------------------------------
    solver.Solve()
    z_lp = solver.Objective().Value()
    bound = int(z_lp + EPS)
    n_frac = 0
    for k in range(len(xs)):
        v = xs[k].solution_value()
        if EPS < v < 1 - EPS:
            n_frac += 1
    log("  z_LP = %.4f  -> can tren K* <= %d ; so bien phan so = %d" % (z_lp, bound, n_frac))
    if args.duals:
        print_duals(inst, M)

    # ------------------------------------------------------------------
    # Bước 2a: rounding
    # ------------------------------------------------------------------
    if args.mode == "round":
        chosen = round_solution(inst, M)
        assign = greedy(inst, fixed=chosen)
        status = "OPTIMAL" if len(assign) == bound else "FEASIBLE"
        return assign, {"status": status, "bound": bound}

    # ------------------------------------------------------------------
    # Bước 2b: diving - cố định dần các biến rồi giải lại LP
    # ------------------------------------------------------------------
    fixed = [False] * len(xs)
    val = [0.0] * len(xs)
    iteration = 0
    while True:
        iteration += 1
        # (a) đọc toàn bộ nghiệm LP hiện tại vào mảng TRƯỚC khi sửa mô hình
        for k in range(len(xs)):
            val[k] = xs[k].solution_value()
        # (b) tìm biến phân số lớn nhất
        best_k = -1
        best_val = -1.0
        integral = True
        for k in range(len(xs)):
            if fixed[k]:
                continue
            if val[k] >= 1 - EPS:
                xs[k].SetLb(1.0)            # biến đã = 1 -> cố định luôn
                fixed[k] = True
            elif val[k] > EPS:
                integral = False
                if val[k] > best_val:
                    best_val = val[k]
                    best_k = k
        if integral:
            break
        # (c) cố định biến phân số lớn nhất = 1 rồi giải lại LP (warm start)
        xs[best_k].SetLb(1.0)
        fixed[best_k] = True
        st = solver.Solve()
        if st != pywraplp.Solver.OPTIMAL:   # không nên xảy ra; phòng hờ
            log("  LP khong toi uu o vong %d -> dung" % iteration)
            break
    log("  so vong diving = %d" % iteration)

    chosen = []
    for k in range(len(xs)):
        if val[k] > 0.5:
            chosen.append((M["var_c"][k], M["var_u"][k], M["var_t"][k]))
    assign = greedy(inst, fixed=chosen)     # lấp chỗ trống nếu còn
    status = "OPTIMAL" if len(assign) == bound else "FEASIBLE"
    return assign, {"status": status, "bound": bound, "z_lp": z_lp}


if __name__ == "__main__":
    run_main(solve, NAME, 60.0, add_args)
