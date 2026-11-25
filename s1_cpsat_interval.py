# -*- coding: utf-8 -*-
"""
s1_cpsat_interval.py - CONSTRAINT PROGRAMMING (CP-SAT) với biến khoảng (interval)
================================================================================
Đây là mô hình được khuyên dùng (nhanh nhất, chạy được instance lớn).

Biến (xem mục "Mô hình 1" trong file modeling):
  a[c]      ∈ {0,1}  : lớp-môn c được xếp (có kíp và có giáo viên)
  u[c]      ∈ U_c    : kíp bắt đầu của c   (miền chỉ chứa kíp hợp lệ -> tự động nằm trọn 1 buổi)
  y[c][t]   ∈ {0,1}  : giáo viên t dạy lớp-môn c  (t ∈ T_c)
  I[c]      = khoảng tùy chọn [u[c], u[c]+d_c) , có mặt khi a[c] = 1
  J[c][t]   = khoảng tùy chọn [u[c], u[c]+d_c) , có mặt khi y[c][t] = 1

Ràng buộc:
  (1) sum_t y[c][t] = a[c]                        mỗi lớp-môn được xếp có đúng 1 giáo viên
  (2) NoOverlap({ I[c] : cls[c] = i })   ∀ lớp i   lớp-môn cùng lớp không chồng lấp
  (3) NoOverlap({ J[c][t] : t ∈ T_c })   ∀ gv t    lớp-môn cùng giáo viên không chồng lấp
  (4) [dư thừa] sum_c d_c * a[c]    <= 60  ∀ lớp i
      [dư thừa] sum_c d_c * y[c][t] <= 60  ∀ gv t
  (5) [dư thừa, theo buổi] sum_c f(d_c) * a[c]    <= 2*10  ∀ lớp i
                            sum_c f(d_c) * y[c][t] <= 2*10  ∀ gv t
      với f(d) = 2 nếu d > 3, 1 nếu d = 3, 0 nếu d < 3   (2 lớp-môn dài > 3 tiết
      không thể chung 1 buổi 6 tiết). Ràng buộc dư thừa không đổi tập nghiệm
      nhưng giúp CP-SAT có cận trên tốt hơn để chứng minh tối ưu.
Mục tiêu:  max sum_c a[c]

Cách chạy:
    python s1_cpsat_interval.py tests/example.txt -t 30 [--workers 8] [--no-hint]
"""

from ortools.sat.python import cp_model
from common import run_main, greedy, NUM_SLOTS, BLOCK_LENGTH

NAME = "CP-SAT interval"


def add_args(parser):
    parser.add_argument("--workers", type=int, default=8, help="so luong tim kiem song song")
    parser.add_argument("--no-hint", action="store_true", help="khong dung loi giai greedy lam goi y")
    parser.add_argument("--no-redundant", action="store_true", help="tat rang buoc du thua (4), (5)")


def solve(inst, time_limit, args):
    model = cp_model.CpModel()
    L = inst.L

    # ------------------------------------------------------------------
    # Bước 1: tạo biến cho từng lớp-môn
    # ------------------------------------------------------------------
    a = [None] * L          # a[c]
    u = [None] * L          # u[c]
    y = []                  # y[c] = dict {t: BoolVar}
    I = [None] * L          # khoảng của lớp-môn c (dùng cho ràng buộc lớp)
    J = []                  # J[c] = dict {t: IntervalVar} (dùng cho ràng buộc giáo viên)
    for c in range(L):
        y.append({})
        J.append({})
        if not inst.schedulable(c):
            continue                    # không có giáo viên / không có kíp -> bỏ qua (a = 0)
        dc = inst.dur[c]
        a[c] = model.NewBoolVar("a_%d" % c)
        # miền của u[c] chỉ gồm các kíp bắt đầu hợp lệ U_c
        u[c] = model.NewIntVarFromDomain(cp_model.Domain.FromValues(inst.UC[c]), "u_%d" % c)
        I[c] = model.NewOptionalFixedSizeIntervalVar(u[c], dc, a[c], "I_%d" % c)
        for t in inst.TC[c]:
            y[c][t] = model.NewBoolVar("y_%d_%d" % (c, t))
            J[c][t] = model.NewOptionalFixedSizeIntervalVar(u[c], dc, y[c][t], "J_%d_%d" % (c, t))

    # ------------------------------------------------------------------
    # Bước 2: (1) mỗi lớp-môn được xếp có đúng một giáo viên
    # ------------------------------------------------------------------
    for c in range(L):
        if a[c] is None:
            continue
        terms = []
        for t in inst.TC[c]:
            terms.append(y[c][t])
        model.Add(sum(terms) == a[c])

    # Hệ số f(d) của ràng buộc dư thừa (5) - "dual feasible function" của bài toán xếp thùng:
    #   mỗi khối (buổi) dài P tiết; lớp-môn dài hơn P/2 chiếm trọn "1 chỗ lớn" của khối,
    #   lớp-môn dài đúng P/2 chiếm nửa chỗ, lớp-môn ngắn hơn P/2 không tính.
    #   => sum_c f(d_c) <= 2 * (số khối)       với f(d) = 2 nếu 2d > P, 1 nếu 2d = P, 0 nếu 2d < P
    P = BLOCK_LENGTH[inst.rule]
    num_blocks = NUM_SLOTS // P
    f = [0] * L
    for c in range(L):
        if 2 * inst.dur[c] > P:
            f[c] = 2
        elif 2 * inst.dur[c] == P:
            f[c] = 1

    # ------------------------------------------------------------------
    # Bước 3: (2) NoOverlap theo lớp  +  (4), (5) ràng buộc dư thừa
    # ------------------------------------------------------------------
    for i in range(1, inst.N + 1):
        intervals = []
        load = []
        big = []
        for c in inst.lm_of_class[i]:
            if I[c] is not None:
                intervals.append(I[c])
                load.append(inst.dur[c] * a[c])
                if f[c] > 0:
                    big.append(f[c] * a[c])
        if len(intervals) > 1:
            model.AddNoOverlap(intervals)
            if not args.no_redundant:
                model.Add(sum(load) <= NUM_SLOTS)
                if len(big) > 0:
                    model.Add(sum(big) <= 2 * num_blocks)

    # ------------------------------------------------------------------
    # Bước 4: (3) NoOverlap theo giáo viên  +  (4), (5) dư thừa
    # ------------------------------------------------------------------
    for t in range(1, inst.T + 1):
        intervals = []
        load = []
        big = []
        for c in inst.lm_of_teacher[t]:
            if t in J[c]:
                intervals.append(J[c][t])
                load.append(inst.dur[c] * y[c][t])
                if f[c] > 0:
                    big.append(f[c] * y[c][t])
        if len(intervals) > 1:
            model.AddNoOverlap(intervals)
            if not args.no_redundant:
                model.Add(sum(load) <= NUM_SLOTS)
                if len(big) > 0:
                    model.Add(sum(big) <= 2 * num_blocks)

    # ------------------------------------------------------------------
    # Bước 5: mục tiêu  max sum a[c]
    # ------------------------------------------------------------------
    obj = []
    for c in range(L):
        if a[c] is not None:
            obj.append(a[c])
    model.Maximize(sum(obj))

    # ------------------------------------------------------------------
    # Bước 6: gợi ý lời giải ban đầu từ greedy (warm start)
    # ------------------------------------------------------------------
    if not args.no_hint:
        g = greedy(inst)
        chosen_u = [0] * L
        chosen_t = [0] * L
        for (c, uu, tt) in g:
            chosen_u[c] = uu
            chosen_t[c] = tt
        for c in range(L):
            if a[c] is None:
                continue
            if chosen_u[c] > 0:
                model.AddHint(a[c], 1)
                model.AddHint(u[c], chosen_u[c])
            else:
                model.AddHint(a[c], 0)
            for t in inst.TC[c]:
                if t == chosen_t[c]:
                    model.AddHint(y[c][t], 1)
                else:
                    model.AddHint(y[c][t], 0)

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
            if a[c] is None or solver.Value(a[c]) == 0:
                continue
            teacher = 0
            for t in inst.TC[c]:
                if solver.Value(y[c][t]) == 1:
                    teacher = t
            assign.append((c, solver.Value(u[c]), teacher))
    info = {"status": solver.StatusName(status),
            "bound": int(round(solver.BestObjectiveBound()))}
    return assign, info


if __name__ == "__main__":
    run_main(solve, NAME, 30.0, add_args)
