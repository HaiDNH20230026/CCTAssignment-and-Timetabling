# -*- coding: utf-8 -*-
"""
s5_mip_bigm.py - INTEGER PROGRAMMING, công thức "big-M" (ràng buộc hoặc-hoặc / disjunctive)
==========================================================================================
Biến thời gian là số nguyên (kíp bắt đầu), không có chỉ số thời gian.
Hai lớp-môn xung đột thì "c1 trước c2" HOẶC "c2 trước c1" -> mô hình hóa bằng
biến thứ tự nhị phân w và hằng số big-M (kỹ thuật either-or constraint của IP).

Biến (xem mục "Mô hình 4" trong file modeling):
  a[c]    ∈ {0,1}          : lớp-môn c được xếp
  y[c,t]  ∈ {0,1}          : giáo viên t dạy c       (t ∈ T_c)
  b[c]    ∈ {0..B-1}       : chỉ số khối (buổi) của c, B = 60 / P   (P = 6 với rule session)
  o[c]    ∈ {0..P-d_c}     : vị trí bắt đầu trong khối
  u[c]    = 1 + P*b[c] + o[c]  (biểu thức tuyến tính - kíp bắt đầu, luôn hợp lệ)
  w[c1,c2] ∈ {0,1}         : = 1 nếu c1 xếp trước c2

Ràng buộc (BIG = 60 đủ lớn vì u1 + d1 - u2 <= 60):
  (1) sum_t y[c,t] = a[c]                                                       ∀ c
  (2) ∀ (c1,c2) ∈ Q_lop :
        u1 + d1 <= u2 + BIG*(1 - w) + BIG*(2 - a1 - a2)
        u2 + d2 <= u1 + BIG*w       + BIG*(2 - a1 - a2)
  (3) ∀ (c1,c2) ∈ Q_gv, ∀ t ∈ T_c1 ∩ T_c2 :
        u1 + d1 <= u2 + BIG*(1 - w) + BIG*(2 - y1t - y2t)
        u2 + d2 <= u1 + BIG*w       + BIG*(2 - y1t - y2t)
Mục tiêu: max sum a[c]

Ràng buộc (2), (3) chính là kỹ thuật tuyến tính hóa "If-then" trong slide IP:
  "nếu a1 = a2 = 1 (cả hai được xếp) thì c1, c2 không chồng lấp".

Nhược điểm: nới lỏng LP rất yếu (chỉ cần w = 0.5 là mọi ràng buộc thỏa) nên
branch-and-bound phải phân nhánh rất nhiều -> chỉ dùng được với instance nhỏ.
File này để MINH HỌA kỹ thuật big-M và so sánh với công thức time-indexed (s4).
Tùy chọn --cuts thêm bất đẳng thức hợp lệ (cutting planes) để làm chặt nới lỏng LP.

Cách chạy:
    python s5_mip_bigm.py tests/example.txt -t 60 [--solver SCIP] [--cuts]
"""

from ortools.linear_solver import pywraplp
from common import (run_main, greedy, log, NUM_SLOTS, BLOCK_LENGTH,
                    class_conflict_pairs, teacher_conflict_pairs)

NAME = "MIP big-M"


def add_args(parser):
    parser.add_argument("--solver", default="SCIP", choices=["SCIP", "CBC", "SAT"])
    parser.add_argument("--no-hint", action="store_true")
    parser.add_argument("--cuts", action="store_true", help="them bat dang thuc hop le (cutting planes)")


def solve(inst, time_limit, args):
    solver = pywraplp.Solver.CreateSolver(args.solver)
    L = inst.L
    d = inst.dur
    P = BLOCK_LENGTH[inst.rule]
    B = NUM_SLOTS // P
    BIG = NUM_SLOTS

    # ------------------------------------------------------------------
    # Bước 1: biến a, y, b, o  và biểu thức u = 1 + P*b + o
    # ------------------------------------------------------------------
    a = [None] * L
    y = []
    bvar = [None] * L
    ovar = [None] * L
    u = [None] * L
    for c in range(L):
        y.append({})
        if not inst.schedulable(c):
            continue
        a[c] = solver.BoolVar("a_%d" % c)
        bvar[c] = solver.IntVar(0, B - 1, "b_%d" % c)
        ovar[c] = solver.IntVar(0, P - d[c], "o_%d" % c)
        u[c] = 1 + P * bvar[c] + ovar[c]
        terms = []
        for t in inst.TC[c]:
            y[c][t] = solver.BoolVar("y_%d_%d" % (c, t))
            terms.append(y[c][t])
        solver.Add(solver.Sum(terms) == a[c])                 # (1)

    # ------------------------------------------------------------------
    # Bước 2: (2) cặp cùng lớp
    # ------------------------------------------------------------------
    w = {}
    n_pair = 0
    for (c1, c2) in class_conflict_pairs(inst):
        w12 = solver.BoolVar("w_%d_%d" % (c1, c2))
        w[(c1, c2)] = w12
        relax = BIG * (2 - a[c1] - a[c2])
        solver.Add(u[c1] + d[c1] <= u[c2] + BIG * (1 - w12) + relax)
        solver.Add(u[c2] + d[c2] <= u[c1] + BIG * w12 + relax)
        n_pair += 1

    # ------------------------------------------------------------------
    # Bước 3: (3) cặp có thể cùng giáo viên
    # ------------------------------------------------------------------
    for (c1, c2, common) in teacher_conflict_pairs(inst):
        w12 = solver.BoolVar("w_%d_%d" % (c1, c2))
        w[(c1, c2)] = w12
        for t in common:
            relax = BIG * (2 - y[c1][t] - y[c2][t])
            solver.Add(u[c1] + d[c1] <= u[c2] + BIG * (1 - w12) + relax)
            solver.Add(u[c2] + d[c2] <= u[c1] + BIG * w12 + relax)
        n_pair += 1
    # ------------------------------------------------------------------
    # Bước 3b (tùy chọn --cuts): thêm BẤT ĐẲNG THỨC HỢP LỆ (valid inequalities / cutting planes)
    #   ∀ lớp i : sum d_c a_c <= 60 ,        sum f(d_c) a_c <= 2B
    #   ∀ gv t  : sum d_c y_ct <= 60 ,       sum f(d_c) y_ct <= 2B
    # Mọi lời giải nguyên đều thỏa (nên "hợp lệ"), nhưng chúng cắt bỏ nhiều nghiệm phân số
    # của nới lỏng LP big-M -> cận trên tốt hơn hẳn. (Bên CP gọi là "ràng buộc dư thừa".)
    # ------------------------------------------------------------------
    if args.cuts:
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
                if a[c] is not None:
                    load.append(d[c] * a[c])
                    big.append(f[c] * a[c])
            if len(load) > 1:
                solver.Add(solver.Sum(load) <= NUM_SLOTS)
                solver.Add(solver.Sum(big) <= 2 * B)
        for t in range(1, inst.T + 1):
            load = []
            big = []
            for c in inst.lm_of_teacher[t]:
                if t in y[c]:
                    load.append(d[c] * y[c][t])
                    big.append(f[c] * y[c][t])
            if len(load) > 1:
                solver.Add(solver.Sum(load) <= NUM_SLOTS)
                solver.Add(solver.Sum(big) <= 2 * B)

    log("  so cap xung dot = %d, so bien = %d, so rang buoc = %d"
        % (n_pair, solver.NumVariables(), solver.NumConstraints()))

    # ------------------------------------------------------------------
    # Bước 4: mục tiêu
    # ------------------------------------------------------------------
    obj = []
    for c in range(L):
        if a[c] is not None:
            obj.append(a[c])
    solver.Maximize(solver.Sum(obj))

    # ------------------------------------------------------------------
    # Bước 5: MIP start từ greedy (gán đủ a, y, b, o, w)
    # ------------------------------------------------------------------
    if not args.no_hint:
        gu = [0] * L
        gt = [0] * L
        for (c, uu, tt) in greedy(inst):
            gu[c] = uu
            gt[c] = tt
        hv = []
        hval = []
        for c in range(L):
            if a[c] is None:
                continue
            start = gu[c] if gu[c] > 0 else 1        # lớp-môn không xếp: để kíp 1
            hv.append(a[c]); hval.append(1.0 if gu[c] > 0 else 0.0)
            hv.append(bvar[c]); hval.append(float((start - 1) // P))
            hv.append(ovar[c]); hval.append(float((start - 1) % P))
            for t in inst.TC[c]:
                hv.append(y[c][t]); hval.append(1.0 if gt[c] == t else 0.0)
        for key in w:
            c1 = key[0]
            c2 = key[1]
            s1 = gu[c1] if gu[c1] > 0 else 1
            s2 = gu[c2] if gu[c2] > 0 else 1
            hv.append(w[key]); hval.append(1.0 if s1 < s2 else 0.0)
        solver.SetHint(hv, hval)

    # ------------------------------------------------------------------
    # Bước 6: giải
    # ------------------------------------------------------------------
    solver.SetTimeLimit(int(time_limit * 1000))
    status = solver.Solve()
    names = {pywraplp.Solver.OPTIMAL: "OPTIMAL", pywraplp.Solver.FEASIBLE: "FEASIBLE",
             pywraplp.Solver.INFEASIBLE: "INFEASIBLE", pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED"}
    status_name = names.get(status, str(status))
    assign = []
    bound = "?"
    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        for c in range(L):
            if a[c] is None or a[c].solution_value() < 0.5:
                continue
            start = 1 + P * int(round(bvar[c].solution_value())) + int(round(ovar[c].solution_value()))
            teacher = 0
            for t in inst.TC[c]:
                if y[c][t].solution_value() > 0.5:
                    teacher = t
            assign.append((c, start, teacher))
        try:
            bound = int(solver.Objective().BestBound() + 1e-6)
        except Exception:
            bound = "?"
    # CBC không dùng hint -> nếu solver hết giờ với lời giải kém hơn greedy thì trả greedy
    g_sol = greedy(inst)
    if len(assign) < len(g_sol):
        log("  solver dung voi K=%d < greedy K=%d -> tra ve greedy" % (len(assign), len(g_sol)))
        assign = g_sol
        status_name += " (greedy)"
    return assign, {"status": status_name, "bound": bound}


if __name__ == "__main__":
    run_main(solve, NAME, 60.0, add_args)
