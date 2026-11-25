# -*- coding: utf-8 -*-
"""
s3_cp_classic.py - CONSTRAINT PROGRAMMING với CP solver "cổ điển" của OR-Tools (pywrapcp)
========================================================================================
Cùng mô hình CSP như s2 (biến x[c], g[c] nguyên, ràng buộc "hoặc"), nhưng giải bằng
solver CP truyền thống: LAN TRUYỀN RÀNG BUỘC (constraint propagation) + CÂY TÌM KIẾM
(DecisionBuilder / Phase) + NHÁNH CẬN (OptimizeVar).  Đây là đúng sơ đồ lý thuyết CP:
    chọn biến -> gán giá trị -> lan truyền -> nếu miền rỗng thì quay lui.
(Slide dùng CP-SAT; solver cổ điển này cũng thuộc OR-Tools, dùng ở đây để thấy rõ vai trò
 của chiến lược phân nhánh - phần "Searching" của slide CP.)

Biến:
  z[c] ∈ {0,1}        : lớp-môn c được xếp
  x[c] ∈ {0} ∪ U_c    : kíp bắt đầu (0 = không xếp)
  g[c] ∈ {0} ∪ T_c    : giáo viên    (0 = không xếp)
Ràng buộc:
  (1) z[c] = (x[c] != 0) ,  z[c] = (g[c] != 0)
  (2) ∀ (c1,c2) ∈ Q_lop : (x1 = 0) + (x2 = 0) + (x1 + d1 <= x2) + (x2 + d2 <= x1) >= 1
  (3) ∀ (c1,c2) ∈ Q_gv  : (g1 != g2) + (x1 = 0) + (x1 + d1 <= x2) + (x2 + d2 <= x1) >= 1
      (mỗi biểu thức so sánh trong pywrapcp là một biến 0/1 nên "hoặc" = tổng >= 1)
  (4) Ràng buộc dư thừa theo lớp / giáo viên (giống s1, s2)
  (5) Cận dưới từ greedy: sum z >= K_greedy + 1  (chỉ tìm lời giải TỐT HƠN greedy)
Mục tiêu: max sum z[c]

Chiến lược tìm kiếm (DecisionBuilder) 3 pha:
  z (thử 1 trước)  ->  x (first-fail: miền nhỏ nhất trước)  ->  g (first-fail).

Nếu cây tìm kiếm duyệt hết mà không có lời giải tốt hơn greedy
=> greedy là tối ưu (chứng minh bằng CP).

Cách chạy:
    python s3_cp_classic.py tests/example.txt -t 30
"""

import time
from ortools.constraint_solver import pywrapcp
from common import (run_main, greedy, class_conflict_pairs, teacher_conflict_pairs,
                    NUM_SLOTS, BLOCK_LENGTH)

NAME = "CP classic (pywrapcp)"


def add_args(parser):
    pass


def solve(inst, time_limit, args):
    L = inst.L
    d = inst.dur
    solver = pywrapcp.Solver("timetabling")

    # ------------------------------------------------------------------
    # Bước 1: lời giải greedy -> cận dưới
    # ------------------------------------------------------------------
    g_sol = greedy(inst)
    K_greedy = len(g_sol)

    # ------------------------------------------------------------------
    # Bước 2: biến
    # ------------------------------------------------------------------
    x = [None] * L
    g = [None] * L
    z = [None] * L
    for c in range(L):
        if not inst.schedulable(c):
            continue
        dom_x = [0]
        for uu in inst.UC[c]:
            dom_x.append(uu)
        dom_g = [0]
        for t in inst.TC[c]:
            dom_g.append(t)
        x[c] = solver.IntVar(dom_x, "x_%d" % c)
        g[c] = solver.IntVar(dom_g, "g_%d" % c)
        z[c] = solver.BoolVar("z_%d" % c)
        # (1)  z = [x != 0] = [g != 0]
        solver.Add(z[c] == (x[c] != 0))
        solver.Add(z[c] == (g[c] != 0))

    # ------------------------------------------------------------------
    # Bước 3: ràng buộc (2) cùng lớp
    # ------------------------------------------------------------------
    for (c1, c2) in class_conflict_pairs(inst):
        solver.Add((x[c1] == 0) + (x[c2] == 0)
                   + (x[c1] + d[c1] <= x[c2]) + (x[c2] + d[c2] <= x[c1]) >= 1)

    # ------------------------------------------------------------------
    # Bước 4: ràng buộc (3) cùng giáo viên
    # ------------------------------------------------------------------
    for (c1, c2, common) in teacher_conflict_pairs(inst):
        solver.Add((g[c1] != g[c2]) + (x[c1] == 0)
                   + (x[c1] + d[c1] <= x[c2]) + (x[c2] + d[c2] <= x[c1]) >= 1)

    # ------------------------------------------------------------------
    # Bước 4b: ràng buộc DƯ THỪA (giống s1, s2) - tăng sức lan truyền
    #   ∀ lớp i : sum d_c z_c <= 60 ,          sum f(d_c) z_c <= 2*số_khối
    #   ∀ gv t  : sum d_c [g_c = t] <= 60 ,    sum f(d_c) [g_c = t] <= 2*số_khối
    # ------------------------------------------------------------------
    P = BLOCK_LENGTH[inst.rule]
    num_blocks = NUM_SLOTS // P
    f = [0] * L
    for c in range(L):
        if 2 * d[c] > P:
            f[c] = 2
        elif 2 * d[c] == P:
            f[c] = 1
    for i in range(1, inst.N + 1):
        load = []
        big = []
        for c in inst.lm_of_class[i]:
            if z[c] is not None:
                load.append(z[c] * d[c])
                if f[c] > 0:
                    big.append(z[c] * f[c])
        if len(load) > 1:
            solver.Add(solver.Sum(load) <= NUM_SLOTS)
        if len(big) > 1:
            solver.Add(solver.Sum(big) <= 2 * num_blocks)
    for t in range(1, inst.T + 1):
        load = []
        big = []
        for c in inst.lm_of_teacher[t]:
            if g[c] is None:
                continue
            y = (g[c] == t).Var()            # biến 0/1 = [g_c = t]  (ràng buộc kênh)
            load.append(y * d[c])
            if f[c] > 0:
                big.append(y * f[c])
        if len(load) > 1:
            solver.Add(solver.Sum(load) <= NUM_SLOTS)
        if len(big) > 1:
            solver.Add(solver.Sum(big) <= 2 * num_blocks)

    # ------------------------------------------------------------------
    # Bước 5: mục tiêu + cận dưới từ greedy
    # ------------------------------------------------------------------
    z_list = []
    for c in range(L):
        if z[c] is not None:
            z_list.append(z[c])
    if len(z_list) == 0:
        return [], {"status": "OPTIMAL", "bound": 0}
    obj = solver.Sum(z_list).Var()
    solver.Add(obj >= K_greedy + 1)
    objective = solver.Maximize(obj, 1)

    # ------------------------------------------------------------------
    # Bước 6: chiến lược tìm kiếm (DecisionBuilder) gồm 3 pha:
    #   pha 1: quyết định TẬP lớp-môn được xếp: gán z[c], thử 1 trước (thứ tự "khó trước")
    #   pha 2: gán kíp x[c] theo nguyên lý FIRST-FAIL: chọn biến có miền NHỎ nhất
    #          (lớp-môn bị lan truyền thu hẹp nhiều nhất), thử kíp nhỏ nhất trước
    #   pha 3: gán giáo viên g[c], cũng first-fail
    # (Thực nghiệm: duyệt (z,x,g) xen kẽ theo thứ tự cố định cần hàng triệu nhánh vẫn chưa
    #  xong trên tests/tiny_1.txt; chiến lược 3 pha này chứng minh tối ưu sau ~60 nhánh.)
    # ------------------------------------------------------------------
    order = []
    for c in range(L):
        if z[c] is not None:
            order.append((len(inst.TC[c]), -d[c], c))
    order.sort()
    z_vars = []
    x_vars = []
    g_vars = []
    for item in order:
        c = item[2]
        z_vars.append(z[c])
        x_vars.append(x[c])
        g_vars.append(g[c])
    db = solver.Compose([
        solver.Phase(z_vars, solver.CHOOSE_FIRST_UNBOUND, solver.ASSIGN_MAX_VALUE),
        solver.Phase(x_vars, solver.CHOOSE_MIN_SIZE_LOWEST_MIN, solver.ASSIGN_MIN_VALUE),
        solver.Phase(g_vars, solver.CHOOSE_MIN_SIZE, solver.ASSIGN_MIN_VALUE),
    ])

    # ------------------------------------------------------------------
    # Bước 7: giải với giới hạn thời gian, giữ lời giải cuối cùng (tốt nhất)
    # ------------------------------------------------------------------
    collector = solver.LastSolutionCollector()
    for c in range(L):
        if z[c] is not None:
            collector.Add(z[c])
            collector.Add(x[c])
            collector.Add(g[c])
    collector.AddObjective(obj)
    limit = solver.TimeLimit(int(time_limit * 1000))
    t0 = time.time()
    solver.Solve(db, [objective, collector, limit])
    elapsed = time.time() - t0
    finished = elapsed < time_limit * 0.98          # duyệt hết cây trước khi hết giờ?

    # ------------------------------------------------------------------
    # Bước 8: lấy kết quả
    # ------------------------------------------------------------------
    if collector.SolutionCount() == 0:
        # không có lời giải nào tốt hơn greedy
        if finished:
            status = "OPTIMAL"
            bound = K_greedy
        else:
            status = "FEASIBLE"
            bound = "?"
        return g_sol, {"status": status + " (greedy)", "bound": bound,
                       "branches": solver.Branches(), "failures": solver.Failures()}

    k = collector.SolutionCount() - 1
    assign = []
    for c in range(L):
        if z[c] is not None and collector.Value(k, z[c]) == 1:
            assign.append((c, collector.Value(k, x[c]), collector.Value(k, g[c])))
    if finished:
        status = "OPTIMAL"
        bound = len(assign)
    else:
        status = "FEASIBLE"
        bound = "?"
    return assign, {"status": status, "bound": bound,
                    "branches": solver.Branches(), "failures": solver.Failures()}


if __name__ == "__main__":
    run_main(solve, NAME, 30.0, add_args)
