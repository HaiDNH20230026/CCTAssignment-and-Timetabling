# -*- coding: utf-8 -*-
"""
s4_mip_time_indexed.py - INTEGER PROGRAMMING, công thức "chỉ số thời gian" (time-indexed)
=======================================================================================
Biến quyết định nhị phân 3 chỉ số (giống x_ij của bài Balanced Class Teacher Assignment
trong slide, thêm chỉ số thời gian):

  x[c,t,u] ∈ {0,1}  = 1 nếu lớp-môn c do giáo viên t dạy, bắt đầu ở kíp u
                       (chỉ tạo với t ∈ T_c, u ∈ U_c)

Ký hiệu phủ:  lớp-môn c bắt đầu ở u "phủ" kíp s  <=>  u <= s <= u + d_c - 1

Ràng buộc:
  (1) sum_{t ∈ T_c} sum_{u ∈ U_c} x[c,t,u] <= 1                                ∀ c
        (mỗi lớp-môn xếp nhiều nhất 1 lần)
  (2) sum_{c: cls[c]=i} sum_{t} sum_{u phủ s} x[c,t,u] <= 1                     ∀ lớp i, ∀ kíp s
        (tại mỗi kíp, lớp i học nhiều nhất 1 lớp-môn)
  (3) sum_{c: t ∈ T_c} sum_{u phủ s} x[c,t,u] <= 1                              ∀ gv t, ∀ kíp s
        (tại mỗi kíp, giáo viên t dạy nhiều nhất 1 lớp-môn)
Mục tiêu: max sum x[c,t,u]

Ràng buộc (2), (3) là ràng buộc "clique" (mọi cặp biến trong đó đều xung đột) nên
nới lỏng LP của công thức này chặt hơn nhiều so với công thức big-M (s5).

Có thể chọn backend MIP: SCIP (mặc định), CBC, SAT (= CP-SAT, như ví dụ trong slide IP).
(HiGHS qua pywraplp bị lỗi khi dùng SetHint và in log ra stdout nên không dùng ở đây.)

Cách chạy:
    python s4_mip_time_indexed.py tests/example.txt -t 60 [--solver SCIP]
"""

from ortools.linear_solver import pywraplp
from common import run_main, greedy, NUM_SLOTS, log

NAME = "MIP time-indexed"


def add_args(parser):
    parser.add_argument("--solver", default="SCIP", choices=["SCIP", "CBC", "SAT"])
    parser.add_argument("--no-hint", action="store_true")


def build_time_indexed(inst, solver, integer):
    """
    Dựng mô hình time-indexed lên 'solver' (pywraplp) theo đúng cách viết trong slide
    (solver.IntVar / solver.Constraint(lb, ub) + SetCoefficient / solver.Objective()).
    Dùng lại cho s6 (LP) và s7 (B&B).
    integer = True  -> x ∈ {0,1} (IntVar);  False -> 0 <= x <= 1 (NumVar, nới lỏng LP)
    Trả về dict chứa:
      var_c, var_t, var_u : mảng thông tin của từng biến k (k = 0..V-1)
      xs                  : mảng biến x_k
      row_lm[c]           : list k thuộc ràng buộc (1) của c
      row_class[i][s]     : list k thuộc ràng buộc (2) của (i, s)
      row_teacher[t][s]   : list k thuộc ràng buộc (3) của (t, s)
      cons_class[i][s], cons_teacher[t][s] : đối tượng ràng buộc (để đọc giá trị đối ngẫu)
    """
    var_c = []
    var_t = []
    var_u = []
    xs = []
    row_lm = []
    for c in range(inst.L):
        row_lm.append([])
    row_class = []
    for i in range(inst.N + 1):
        row = []
        for s in range(NUM_SLOTS + 1):
            row.append([])
        row_class.append(row)
    row_teacher = []
    for t in range(inst.T + 1):
        row = []
        for s in range(NUM_SLOTS + 1):
            row.append([])
        row_teacher.append(row)

    # ---------------- BIẾN: x[c,t,u] ----------------
    k = 0
    for c in range(inst.L):
        if not inst.schedulable(c):
            continue
        i = inst.cls[c]
        for t in inst.TC[c]:
            for u in inst.UC[c]:
                name = "x[%d,%d,%d]" % (c, t, u)
                if integer:
                    v = solver.IntVar(0, 1, name)
                else:
                    v = solver.NumVar(0.0, 1.0, name)
                xs.append(v)
                var_c.append(c)
                var_t.append(t)
                var_u.append(u)
                row_lm[c].append(k)
                for s in range(u, u + inst.dur[c]):     # các kíp s mà biến này phủ
                    row_class[i][s].append(k)
                    row_teacher[t][s].append(k)
                k += 1

    inf = solver.infinity()

    # ---------------- RÀNG BUỘC (1): mỗi lớp-môn xếp nhiều nhất 1 lần ----------------
    for c in range(inst.L):
        if len(row_lm[c]) > 0:
            cons1 = solver.Constraint(-inf, 1)
            for kk in row_lm[c]:
                cons1.SetCoefficient(xs[kk], 1)

    # ---------------- RÀNG BUỘC (2): lớp i, kíp s ----------------
    cons_class = []
    for i in range(inst.N + 1):
        cons_class.append([None] * (NUM_SLOTS + 1))
    for i in range(1, inst.N + 1):
        for s in range(1, NUM_SLOTS + 1):
            if len(row_class[i][s]) > 1:
                cons2 = solver.Constraint(-inf, 1)
                for kk in row_class[i][s]:
                    cons2.SetCoefficient(xs[kk], 1)
                cons_class[i][s] = cons2

    # ---------------- RÀNG BUỘC (3): giáo viên t, kíp s ----------------
    cons_teacher = []
    for t in range(inst.T + 1):
        cons_teacher.append([None] * (NUM_SLOTS + 1))
    for t in range(1, inst.T + 1):
        for s in range(1, NUM_SLOTS + 1):
            if len(row_teacher[t][s]) > 1:
                cons3 = solver.Constraint(-inf, 1)
                for kk in row_teacher[t][s]:
                    cons3.SetCoefficient(xs[kk], 1)
                cons_teacher[t][s] = cons3

    # ---------------- MỤC TIÊU: max sum x ----------------
    objective = solver.Objective()
    for kk in range(len(xs)):
        objective.SetCoefficient(xs[kk], 1)
    objective.SetMaximization()

    return {"var_c": var_c, "var_t": var_t, "var_u": var_u, "xs": xs,
            "row_lm": row_lm, "row_class": row_class, "row_teacher": row_teacher,
            "cons_class": cons_class, "cons_teacher": cons_teacher}


def solve(inst, time_limit, args):
    # Bước 1 (import thư viện) ở đầu file.
    # Bước 2: khai báo solver MIP (backend SCIP như trong slide)
    solver = pywraplp.Solver.CreateSolver(args.solver)
    if solver is None:
        log("Khong tao duoc solver %s, chuyen sang CBC" % args.solver)
        solver = pywraplp.Solver.CreateSolver("CBC")

    # Bước 3, 4, 5: biến, ràng buộc, mục tiêu
    M = build_time_indexed(inst, solver, integer=True)
    xs = M["xs"]
    log("  so bien = %d, so rang buoc = %d" % (solver.NumVariables(), solver.NumConstraints()))

    # (thêm) gợi ý lời giải ban đầu từ greedy (MIP start)
    if not args.no_hint and len(xs) > 0:
        start = {}
        for (c, u, t) in greedy(inst):
            start[(c, t, u)] = True
        hint_vars = []
        hint_vals = []
        for k in range(len(xs)):
            key = (M["var_c"][k], M["var_t"][k], M["var_u"][k])
            hint_vars.append(xs[k])
            if key in start:
                hint_vals.append(1.0)
            else:
                hint_vals.append(0.0)
        solver.SetHint(hint_vars, hint_vals)

    # Bước 6: gọi solver
    solver.SetTimeLimit(int(time_limit * 1000))
    status = solver.Solve()

    # Bước 7: lấy lời giải
    names = {pywraplp.Solver.OPTIMAL: "OPTIMAL", pywraplp.Solver.FEASIBLE: "FEASIBLE",
             pywraplp.Solver.INFEASIBLE: "INFEASIBLE", pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED"}
    status_name = names.get(status, str(status))
    assign = []
    bound = "?"
    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        for k in range(len(xs)):
            if xs[k].solution_value() > 0.5:
                assign.append((M["var_c"][k], M["var_u"][k], M["var_t"][k]))
        try:
            bound = int(solver.Objective().BestBound() + 1e-6)
        except Exception:
            bound = "?"
        log("  so nut branch-and-bound = %d" % solver.nodes())
    # nếu solver không có lời giải / lời giải kém hơn greedy (CBC không dùng hint) -> trả greedy
    g_sol = greedy(inst)
    if len(assign) < len(g_sol):
        log("  solver dung voi K=%d < greedy K=%d -> tra ve greedy" % (len(assign), len(g_sol)))
        assign = g_sol
        status_name += " (greedy)"
    return assign, {"status": status_name, "bound": bound}


if __name__ == "__main__":
    run_main(solve, NAME, 60.0, add_args)
