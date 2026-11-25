# -*- coding: utf-8 -*-
"""
checker.py - Kiểm tra một file output có hợp lệ với file input không.

Cách dùng:
    python checker.py input.txt output.txt [--rule session]

Kiểm tra:
  - mỗi dòng "x y u v": lớp x thật sự học môn y, giáo viên v dạy được môn y
  - kíp u hợp lệ (lớp-môn nằm trọn trong 1 buổi nếu rule = session)
  - không lớp-môn nào xuất hiện 2 lần
  - các lớp-môn cùng lớp / cùng giáo viên không chồng lấp
  - K ở dòng 1 khớp với số dòng
"""

import sys
import argparse
from common import read_instance, read_tokens, verify


def check(input_path, output_path, rule):
    inst = read_instance(input_path, rule)

    # index[i][m] = chỉ số lớp-môn c của (lớp i, môn m), -1 nếu lớp i không học môn m
    index = []
    for i in range(inst.N + 1):
        index.append([-1] * (inst.M + 1))
    for c in range(inst.L):
        index[inst.cls[c]][inst.sub[c]] = c

    tok = read_tokens(output_path)
    errors = []
    K = tok[0]
    if len(tok) != 1 + 4 * K:
        errors.append("so token = %d, mong doi 1 + 4*K = %d" % (len(tok), 1 + 4 * K))
    assign = []
    pos = 1
    for k in range(K):
        if pos + 3 >= len(tok):
            break
        x = tok[pos]; y = tok[pos + 1]; u = tok[pos + 2]; v = tok[pos + 3]
        pos += 4
        if x < 1 or x > inst.N or y < 1 or y > inst.M or index[x][y] < 0:
            errors.append("dong %d: lop %d khong hoc mon %d" % (k + 2, x, y))
            continue
        if v < 1 or v > inst.T:
            errors.append("dong %d: giao vien %d khong ton tai" % (k + 2, v))
            continue
        assign.append((index[x][y], u, v))

    errors.extend(verify(inst, assign))
    return K, errors


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--rule", default="session", choices=["session", "day", "week"])
    args = p.parse_args()
    K, errors = check(args.input, args.output, args.rule)
    if len(errors) == 0:
        print("OK  K = %d" % K)
        sys.exit(0)
    print("FAIL (%d loi)" % len(errors))
    for e in errors[:20]:
        print("  - " + e)
    sys.exit(1)


if __name__ == "__main__":
    main()
