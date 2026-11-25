# -*- coding: utf-8 -*-
"""
gen.py - Sinh instance ngẫu nhiên đúng định dạng input của đề bài.

Cách dùng:
    python gen.py T N M [--seed 1] [--min-sub 2] [--max-sub 6]
                        [--teach-min 1] [--teach-max 4] [--dmin 2] [--dmax 4] > input.txt

  - Mỗi lớp học ngẫu nhiên từ min-sub đến max-sub môn.
  - Mỗi giáo viên dạy được từ teach-min đến teach-max môn.
  - Số tiết mỗi môn d(m) trong [dmin, dmax]  (<= 6 để xếp được trong 1 buổi).
"""

import random
import argparse


def generate(T, N, M, seed, min_sub, max_sub, teach_min, teach_max, dmin, dmax):
    rnd = random.Random(seed)
    lines = ["%d %d %d" % (T, N, M)]

    # ---- danh sách môn của từng lớp ----
    for i in range(N):
        k = rnd.randint(min(min_sub, M), min(max_sub, M))
        subjects = rnd.sample(range(1, M + 1), k)
        subjects.sort()
        row = []
        for m in subjects:
            row.append(str(m))
        row.append("0")
        lines.append(" ".join(row))

    # ---- danh sách môn của từng giáo viên ----
    # bảo đảm mỗi môn có ít nhất 1 giáo viên: môn m giao cho giáo viên (m-1) % T trước
    teach = []
    for t in range(T):
        teach.append(set())
    for m in range(1, M + 1):
        teach[(m - 1) % T].add(m)
    for t in range(T):
        k = rnd.randint(min(teach_min, M), min(teach_max, M))
        while len(teach[t]) < k:
            teach[t].add(rnd.randint(1, M))
    for t in range(T):
        subjects = sorted(teach[t])
        row = []
        for m in subjects:
            row.append(str(m))
        row.append("0")
        lines.append(" ".join(row))

    # ---- số tiết ----
    row = []
    for m in range(M):
        row.append(str(rnd.randint(dmin, dmax)))
    lines.append(" ".join(row))
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("T", type=int)
    p.add_argument("N", type=int)
    p.add_argument("M", type=int)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--min-sub", type=int, default=2)
    p.add_argument("--max-sub", type=int, default=6)
    p.add_argument("--teach-min", type=int, default=1)
    p.add_argument("--teach-max", type=int, default=4)
    p.add_argument("--dmin", type=int, default=2)
    p.add_argument("--dmax", type=int, default=4)
    a = p.parse_args()
    print(generate(a.T, a.N, a.M, a.seed, a.min_sub, a.max_sub,
                   a.teach_min, a.teach_max, a.dmin, a.dmax), end="")


if __name__ == "__main__":
    main()
