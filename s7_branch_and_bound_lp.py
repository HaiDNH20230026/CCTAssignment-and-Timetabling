# -*- coding: utf-8 -*-
"""
s7_branch_and_bound_lp.py - INTEGER PROGRAMMING: TỰ CÀI thuật toán NHÁNH CẬN (Branch & Bound)
=============================================================================================
Minh họa đúng thuật toán trong lý thuyết IP (thay vì gọi SCIP/CBC):
  - Mỗi nút = bài toán LP nới lỏng (time-indexed, giải bằng GLOP) + một số biến đã cố định.
  - CẬN (bound):   nếu floor(z_LP) <= K_best   -> tỉa nhánh (vì max, mục tiêu nguyên)
  - Nếu LP vô nghiệm -> tỉa.
  - Nếu nghiệm LP nguyên -> cập nhật lời giải tốt nhất (incumbent).
  - Ngược lại PHÂN NHÁNH trên biến "phân số nhất" x_k (gần 0.5 nhất):
        nhánh 1: x_k = 1      nhánh 2: x_k = 0
  - Duyệt theo chiều sâu (DFS) bằng NGĂN XẾP tường minh, nhánh x_k = 1 được duyệt trước.
  - Incumbent ban đầu lấy từ greedy.

Chỉ phù hợp instance nhỏ - vừa (Python + giải lại LP ở mỗi nút).

Cách chạy:
    python s7_branch_and_bound_lp.py tests/small_2.txt -t 60 [--max-nodes 100000]
"""

import time
from ortools.linear_solver import pywraplp
from common import run_main, greedy, log
from s4_mip_time_indexed import build_time_indexed

NAME = "Branch&Bound (tu cai, LP=GLOP)"
EPS = 1e-6


def add_args(parser):
    parser.add_argument("--max-nodes", type=int, default=1000000)


def solve(inst, time_limit, args):
    t_start = time.time()
    solver = pywraplp.Solver.CreateSolver("GLOP")
    M = build_time_indexed(inst, solver, integer=False)
    xs = M["xs"]
    V = len(xs)

    # ------------------------------------------------------------------
    # Bước 1: incumbent ban đầu từ greedy
    # ------------------------------------------------------------------
    best_assign = greedy(inst)
    K_best = len(best_assign)
    if V == 0:
        return best_assign, {"status": "OPTIMAL", "bound": K_best}

    # ------------------------------------------------------------------
    # Bước 2: ngăn xếp các nút. Mỗi nút = (danh sách cố định [(k, giá trị)], cận của nút cha)
    # ------------------------------------------------------------------
    stack = [([], V)]
    applied = []                 # các biến đang bị đổi cận so với [0,1]
    nodes = 0
    pruned = 0
    root_bound = None
    val = [0.0] * V

    while len(stack) > 0:
        if time.time() - t_start > time_limit or nodes >= args.max_nodes:
            break
        node = stack.pop()
        fixings = node[0]
        parent_ub = node[1]
        if parent_ub <= K_best:              # cận cha đã không còn hứa hẹn
            pruned += 1
            continue
        nodes += 1

        # (a) khôi phục cận [0,1] cho các biến của nút trước, rồi áp dụng cố định của nút này
        for k in applied:
            xs[k].SetBounds(0.0, 1.0)
        applied = []
        for (k, v) in fixings:
            xs[k].SetBounds(float(v), float(v))
            applied.append(k)

        # (b) giải LP nới lỏng tại nút
        status = solver.Solve()
        if status != pywraplp.Solver.OPTIMAL:
            pruned += 1                       # LP vô nghiệm -> tỉa
            continue
        z = solver.Objective().Value()
        ub = int(z + EPS)                     # cận trên nguyên của nhánh
        if root_bound is None:
            root_bound = ub
            log("  nut goc: z_LP = %.4f, can tren = %d, incumbent (greedy) = %d"
                % (z, ub, K_best))
        if ub <= K_best:
            pruned += 1                       # tỉa theo cận
            continue

        # (c) đọc nghiệm và chọn biến phân số nhất
        for k in range(V):
            val[k] = xs[k].solution_value()
        branch_k = -1
        best_frac = 1.0
        for k in range(V):
            v = val[k]
            if EPS < v < 1 - EPS:
                frac = abs(v - 0.5)
                if frac < best_frac:
                    best_frac = frac
                    branch_k = k

        # (d) nghiệm nguyên -> cập nhật incumbent
        if branch_k < 0:
            cand = []
            for k in range(V):
                if val[k] > 0.5:
                    cand.append((M["var_c"][k], M["var_u"][k], M["var_t"][k]))
            if len(cand) > K_best:
                K_best = len(cand)
                best_assign = cand
                log("  incumbent moi K = %d (nut %d, %.2fs)" % (K_best, nodes, time.time() - t_start))
            continue

        # (e) phân nhánh: đẩy nhánh x=0 trước để nhánh x=1 được lấy ra (duyệt) trước
        child0 = []
        for f in fixings:
            child0.append(f)
        child0.append((branch_k, 0))
        child1 = []
        for f in fixings:
            child1.append(f)
        child1.append((branch_k, 1))
        stack.append((child0, ub))
        stack.append((child1, ub))

    # ------------------------------------------------------------------
    # Bước 3: kết luận
    # ------------------------------------------------------------------
    if len(stack) == 0:
        status_name = "OPTIMAL"
        bound = K_best
    else:
        status_name = "FEASIBLE (het gio/nut)"
        bound = K_best
        for node in stack:                    # cận toàn cục = max cận các nút còn mở
            if node[1] > bound:
                bound = node[1]
    log("  so nut = %d, so nhanh bi tia = %d" % (nodes, pruned))
    return best_assign, {"status": status_name, "bound": bound, "nodes": nodes}


if __name__ == "__main__":
    run_main(solve, NAME, 60.0, add_args)
