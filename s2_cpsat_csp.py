# -*- coding: utf-8 -*-
"""
s2_cpsat_csp.py - CONSTRAINT PROGRAMMING (CP-SAT) dạng CSP thuần: biến nguyên + ràng buộc logic
==============================================================================================
Mô hình theo đúng khung COP = (X, D, C, f) của slide Modelling (giống bài N-Queen, Sudoku):
mỗi lớp-môn có 2 biến nguyên, ràng buộc viết bằng phép "hoặc" (disjunction) giữa từng cặp.

Biến (xem mục "Mô hình 2" trong file modeling):
  x[c] ∈ {0} ∪ U_c   : kíp bắt đầu của lớp-môn c, 0 = không xếp
  g[c] ∈ {0} ∪ T_c   : giáo viên dạy lớp-môn c,   0 = không xếp
  z[c] ∈ {0,1}       : z[c] = 1  <=>  x[c] != 0   (biến chỉ thị, dùng cho mục tiêu)

Ràng buộc:
  (1) x[c] = 0  <=>  g[c] = 0                                            ∀ c
  (2) ∀ (c1,c2) ∈ Q_lop :  x[c1]=0  ∨  x[c2]=0  ∨  x[c1]+d1 <= x[c2]  ∨  x[c2]+d2 <= x[c1]
  (3) ∀ (c1,c2) ∈ Q_gv  :  g[c1]≠g[c2]  ∨  x[c1]=0  ∨  x[c1]+d1 <= x[c2]  ∨  x[c2]+d2 <= x[c1]
  (4) [kênh]     y[c][t] = 1 <=> g[c] = t
  (5) [dư thừa]  như (4), (5) của s1, viết trên z[c] và y[c][t]
Mục tiêu:  max sum_c z[c]

Trong CP-SAT mỗi mệnh đề con được biểu diễn bằng một biến Bool với
OnlyEnforceIf (reification một chiều - "half reification"):
  before[c1,c2] => x[c1] + d1 <= x[c2]
  after [c1,c2] => x[c2] + d2 <= x[c1]
  diff  [c1,c2] => g[c1] != g[c2]
rồi ràng buộc (2), (3) trở thành AddBoolOr(...).

Số cặp trong Q_gv tăng ~ L^2 nên mô hình này chậm hơn s1 với instance lớn.

Cách chạy:
    python s2_cpsat_csp.py tests/example.txt -t 30
"""

from ortools.sat.python import cp_model
from common import (run_main, greedy, class_conflict_pairs, teacher_conflict_pairs,
                    NUM_SLOTS, BLOCK_LENGTH)

NAME = "CP-SAT CSP"


def add_args(parser):
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--no-hint", action="store_true")
    parser.add_argument("--no-redundant", action="store_true", help="tat rang buoc kenh + du thua")


def solve(inst, time_limit, args):
    model = cp_model.CpModel()
    L = inst.L
    d = inst.dur

    # ------------------------------------------------------------------
    # Bước 1: biến x[c], g[c], z[c]
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
        x[c] = model.NewIntVarFromDomain(cp_model.Domain.FromValues(dom_x), "x_%d" % c)
        g[c] = model.NewIntVarFromDomain(cp_model.Domain.FromValues(dom_g), "g_%d" % c)
        z[c] = model.NewBoolVar("z_%d" % c)
        # z[c] = 1 <=> x[c] != 0 ;  z[c] = 1 <=> g[c] != 0   => ràng buộc (1)
        model.Add(x[c] != 0).OnlyEnforceIf(z[c])
        model.Add(x[c] == 0).OnlyEnforceIf(z[c].Not())
        model.Add(g[c] != 0).OnlyEnforceIf(z[c])
        model.Add(g[c] == 0).OnlyEnforceIf(z[c].Not())

    # ------------------------------------------------------------------
    # Bước 2: hàm tạo 2 biến Bool before/after cho một cặp (c1, c2)
    # ------------------------------------------------------------------
    def order_literals(c1, c2):
        before = model.NewBoolVar("b_%d_%d" % (c1, c2))
        after = model.NewBoolVar("a_%d_%d" % (c1, c2))
        model.Add(x[c1] + d[c1] <= x[c2]).OnlyEnforceIf(before)
        model.Add(x[c2] + d[c2] <= x[c1]).OnlyEnforceIf(after)
        return before, after

    # ------------------------------------------------------------------
    # Bước 3: ràng buộc (2) - cùng lớp
    # ------------------------------------------------------------------
    for (c1, c2) in class_conflict_pairs(inst):
        before, after = order_literals(c1, c2)
        model.AddBoolOr([z[c1].Not(), z[c2].Not(), before, after])

    # ------------------------------------------------------------------
    # Bước 4: ràng buộc (3) - cùng giáo viên (chỉ cặp có giáo viên chung)
    # ------------------------------------------------------------------
    for (c1, c2, common) in teacher_conflict_pairs(inst):
        before, after = order_literals(c1, c2)
        diff = model.NewBoolVar("diff_%d_%d" % (c1, c2))
        model.Add(g[c1] != g[c2]).OnlyEnforceIf(diff)
        model.AddBoolOr([diff, z[c1].Not(), z[c2].Not(), before, after])

    # ------------------------------------------------------------------
    # Bước 4b: RÀNG BUỘC KÊNH (channeling) + RÀNG BUỘC DƯ THỪA (giống s1)
    #   y[c][t] = 1 <=> g[c] = t   (nối "góc nhìn" biến nguyên g với "góc nhìn" Bool y)
    #   ∀ lớp i : sum d_c z_c <= 60 ,  sum f(d_c) z_c <= 2*số_khối
    #   ∀ gv t  : sum d_c y_ct <= 60 , sum f(d_c) y_ct <= 2*số_khối
    # Không đổi tập nghiệm nhưng giúp lan truyền / cận trên tốt hơn nhiều.
    # ------------------------------------------------------------------
    if not args.no_redundant:
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
                    load.append(d[c] * z[c])
                    big.append(f[c] * z[c])
            if len(load) > 1:
                model.Add(sum(load) <= NUM_SLOTS)
                model.Add(sum(big) <= 2 * num_blocks)
        for t in range(1, inst.T + 1):
            load = []
            big = []
            for c in inst.lm_of_teacher[t]:
                if g[c] is None:
                    continue
                y = model.NewBoolVar("y_%d_%d" % (c, t))
                model.Add(g[c] == t).OnlyEnforceIf(y)
                model.Add(g[c] != t).OnlyEnforceIf(y.Not())
                load.append(d[c] * y)
                big.append(f[c] * y)
            if len(load) > 1:
                model.Add(sum(load) <= NUM_SLOTS)
                model.Add(sum(big) <= 2 * num_blocks)

    # ------------------------------------------------------------------
    # Bước 5: mục tiêu
    # ------------------------------------------------------------------
    obj = []
    for c in range(L):
        if z[c] is not None:
            obj.append(z[c])
    model.Maximize(sum(obj))

    # ------------------------------------------------------------------
    # Bước 6: gợi ý từ greedy
    # ------------------------------------------------------------------
    if not args.no_hint:
        hint_x = [0] * L
        hint_g = [0] * L
        for (c, uu, tt) in greedy(inst):
            hint_x[c] = uu
            hint_g[c] = tt
        for c in range(L):
            if x[c] is None:
                continue
            model.AddHint(x[c], hint_x[c])
            model.AddHint(g[c], hint_g[c])
            if hint_x[c] > 0:
                model.AddHint(z[c], 1)
            else:
                model.AddHint(z[c], 0)

    # ------------------------------------------------------------------
    # Bước 7: giải
    # ------------------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = args.workers
    status = solver.Solve(model)

    assign = []
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        for c in range(L):
            if z[c] is not None and solver.Value(z[c]) == 1:
                assign.append((c, solver.Value(x[c]), solver.Value(g[c])))
    info = {"status": solver.StatusName(status),
            "bound": int(round(solver.BestObjectiveBound()))}
    return assign, info


if __name__ == "__main__":
    run_main(solve, NAME, 30.0, add_args)
