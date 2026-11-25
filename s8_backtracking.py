# -*- coding: utf-8 -*-
"""
s8_backtracking.py - QUAY LUI + NHÁNH CẬN thuần Python (theo slide week06, hàm TRY(k))
=====================================================================================
KHÔNG dùng OR-Tools. Dùng làm lời giải tham chiếu chính xác cho instance rất nhỏ,
để đối chiếu kết quả của các solver OR-Tools.

Duyệt lần lượt lớp-môn k = 0, 1, ..., L-1 (đã sắp "khó trước"). Tập ứng viên A_k:
  - mọi cặp (u, t) với u ∈ U_c, t ∈ T_c sao cho lớp và giáo viên đều rảnh trong [u, u+d_c-1]
  - và lựa chọn "không xếp" (thử sau cùng)

    TRY(k):
      if cur + (số lớp-môn còn lại) <= best: return        # cận
      foreach (u, t) in A_k:
          if check(u, t, k):
              gán x_k = (u, t); cập nhật busy
              if k = L-1: lưu lời giải  else TRY(k+1)
              khôi phục busy
      TRY(k+1) với x_k = "không xếp"

PHÁ ĐỐI XỨNG (symmetry breaking): mọi lớp-môn nằm trọn trong 1 buổi nên các buổi CHƯA
có lớp-môn nào là hoán đổi được cho nhau (10 buổi -> 10! lời giải tương đương).
Vì vậy khi đặt lớp-môn vào một buổi còn trống hoàn toàn, chỉ thử buổi trống có chỉ số
nhỏ nhất. Điều này không làm mất lời giải tối ưu nhưng thu nhỏ cây tìm kiếm rất nhiều.
(Tắt bằng --no-symmetry để so sánh.)

Cách chạy:
    python s8_backtracking.py tests/example.txt -t 30
"""

import sys
import time
from common import run_main, greedy, NUM_SLOTS, BLOCK_LENGTH

NAME = "Backtracking (thuan Python)"


def add_args(parser):
    parser.add_argument("--no-symmetry", action="store_true", help="tat pha doi xung giua cac buoi")


def solve(inst, time_limit, args):
    sys.setrecursionlimit(100000)
    t_start = time.time()

    # ---- thứ tự duyệt: lớp-môn khó trước ----
    order_tmp = []
    for c in range(inst.L):
        if inst.schedulable(c):
            order_tmp.append((len(inst.TC[c]), -inst.dur[c], c))
    order_tmp.sort()
    order = []
    for item in order_tmp:
        order.append(item[2])
    n = len(order)

    # ---- trạng thái dùng chung (cấu trúc dữ liệu D trong slide) ----
    busy_class = []
    for i in range(inst.N + 1):
        busy_class.append([False] * (NUM_SLOTS + 2))
    busy_teacher = []
    for t in range(inst.T + 1):
        busy_teacher.append([False] * (NUM_SLOTS + 2))
    cur_u = [0] * inst.L
    cur_t = [0] * inst.L
    P = BLOCK_LENGTH[inst.rule]               # độ dài 1 khối (buổi)
    num_blocks = NUM_SLOTS // P
    block_count = [0] * num_blocks            # số lớp-môn đang nằm trong khối b
    use_symmetry = not args.no_symmetry

    g = greedy(inst)
    state = {"best": len(g), "best_assign": g, "cur": 0, "timeout": False, "nodes": 0}

    def check(c, u, t):
        i = inst.cls[c]
        for s in range(u, u + inst.dur[c]):
            if busy_class[i][s] or busy_teacher[t][s]:
                return False
        return True

    def mark(c, u, t, value):
        i = inst.cls[c]
        for s in range(u, u + inst.dur[c]):
            busy_class[i][s] = value
            busy_teacher[t][s] = value

    def save_solution():
        if state["cur"] > state["best"]:
            sol = []
            for c in order:
                if cur_u[c] > 0:
                    sol.append((c, cur_u[c], cur_t[c]))
            state["best"] = state["cur"]
            state["best_assign"] = sol

    def TRY(k):
        state["nodes"] += 1
        if state["nodes"] % 2000 == 0 and time.time() - t_start > time_limit:
            state["timeout"] = True
        if state["timeout"]:
            return
        # cận: kể cả xếp được hết phần còn lại cũng không hơn best -> cắt
        if state["cur"] + (n - k) <= state["best"]:
            return
        if k == n:
            save_solution()
            return
        c = order[k]
        # khối trống đầu tiên (dùng cho phá đối xứng)
        first_empty = num_blocks
        for b in range(num_blocks):
            if block_count[b] == 0:
                first_empty = b
                break
        # --- các lựa chọn xếp (u, t) ---
        for u in inst.UC[c]:
            b = (u - 1) // P
            if use_symmetry and block_count[b] == 0 and b != first_empty:
                continue                          # khối trống khác = đối xứng -> bỏ
            for t in inst.TC[c]:
                if check(c, u, t):
                    cur_u[c] = u
                    cur_t[c] = t
                    mark(c, u, t, True)
                    block_count[b] += 1
                    state["cur"] += 1
                    TRY(k + 1)
                    state["cur"] -= 1
                    block_count[b] -= 1
                    mark(c, u, t, False)          # khôi phục D
                    cur_u[c] = 0
                    cur_t[c] = 0
        # --- lựa chọn "không xếp" ---
        TRY(k + 1)

    TRY(0)
    status = "FEASIBLE (het gio)" if state["timeout"] else "OPTIMAL"
    bound = "?" if state["timeout"] else state["best"]
    return state["best_assign"], {"status": status, "bound": bound, "nodes": state["nodes"]}


if __name__ == "__main__":
    run_main(solve, NAME, 30.0, add_args)
