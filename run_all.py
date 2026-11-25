# -*- coding: utf-8 -*-
"""
run_all.py - Chạy nhiều phương pháp trên cùng một input và in bảng so sánh.

Cách dùng:
    python run_all.py tests/small_2.txt -t 30
    python run_all.py tests/large_1.txt -t 60 --only s1,s4,s6
    python run_all.py tests/*.txt -t 20 --fast        (bỏ các phương pháp chỉ hợp instance nhỏ)
    python run_all.py tests/tiny_1.txt --ablation      (thêm các biến thể tắt bớt kỹ thuật)

Cột:  K = số lớp-môn xếp được,  UB = cận trên chứng minh được,  OK = qua checker.
"""

import sys
import time
import argparse
import importlib
from common import read_instance, verify, make_arg_parser

METHODS = [
    # (mã, module, nhãn, chỉ hợp instance nhỏ?, tham số thêm)
    ("s1",  "s1_cpsat_interval",      "CP-SAT interval + NoOverlap", False, []),
    ("s2",  "s2_cpsat_csp",           "CP-SAT CSP (bien nguyen)",    True,  []),
    ("s3",  "s3_cp_classic",          "CP co dien (pywrapcp)",       True,  []),
    ("s4",  "s4_mip_time_indexed",    "MIP time-indexed (SCIP)",     False, []),
    ("s5",  "s5_mip_bigm",            "MIP big-M (SCIP)",            True,  []),
    ("s5c", "s5_mip_bigm",            "MIP big-M + cuts (SCIP)",     True,  ["--cuts"]),
    ("s6",  "s6_lp_relaxation",       "LP relax + diving (GLOP)",    False, []),
    ("s7",  "s7_branch_and_bound_lp", "B&B tu cai tren LP",          True,  []),
    ("s8",  "s8_backtracking",        "Backtracking thuan Python",   True,  []),
]

# Các biến thể "tắt bớt kỹ thuật" để đo tác dụng (chạy với --ablation)
ABLATION = [
    ("s1-", "s1_cpsat_interval", "CP-SAT interval, KHONG du thua", False, ["--no-redundant"]),
    ("s2-", "s2_cpsat_csp",      "CP-SAT CSP, KHONG du thua",      True,  ["--no-redundant"]),
    ("s6r", "s6_lp_relaxation",  "LP relax + rounding (GLOP)",     False, ["--mode", "round"]),
    ("s8-", "s8_backtracking",   "Backtracking, KHONG pha doi xung", True, ["--no-symmetry"]),
]


def run_one(module_name, inst_path, rule, time_limit, extra):
    mod = importlib.import_module(module_name)
    parser = make_arg_parser(module_name, time_limit)
    mod.add_args(parser)
    argv = [inst_path, "--rule", rule, "-t", str(time_limit), "-q"]
    for e in extra:
        argv.append(e)
    args = parser.parse_args(argv)
    inst = read_instance(inst_path, rule)
    t0 = time.time()
    assign, info = mod.solve(inst, time_limit, args)
    elapsed = time.time() - t0
    errors = verify(inst, assign)
    return inst, len(assign), info, elapsed, len(errors) == 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("inputs", nargs="+")
    p.add_argument("-t", "--time", type=float, default=30.0)
    p.add_argument("--rule", default="session", choices=["session", "day", "week"])
    p.add_argument("--only", default=None, help="vd: s1,s4,s6")
    p.add_argument("--fast", action="store_true", help="bo cac phuong phap chi hop instance nho")
    p.add_argument("--ablation", action="store_true", help="chay them cac bien the tat bot ky thuat")
    a = p.parse_args()

    pool = []
    for m in METHODS:
        pool.append(m)
    if a.ablation:
        for m in ABLATION:
            pool.append(m)
    selected = []
    for m in pool:
        if a.only is not None:
            if m[0] in a.only.split(","):
                selected.append(m)
        elif not (a.fast and m[3]):
            selected.append(m)

    for path in a.inputs:
        inst = read_instance(path, a.rule)
        print("=" * 86)
        print("%s : T=%d N=%d M=%d, so lop-mon L=%d (co the xep %d)"
              % (path, inst.T, inst.N, inst.M, inst.L, inst.num_schedulable()))
        print("%-4s %-30s %5s %5s %-24s %8s %4s"
              % ("ma", "phuong phap", "K", "UB", "status", "time(s)", "OK"))
        print("-" * 86)
        for m in selected:
            try:
                inst, K, info, elapsed, ok = run_one(m[1], path, a.rule, a.time, m[4])
                print("%-4s %-30s %5d %5s %-24s %8.2f %4s"
                      % (m[0], m[2], K, str(info.get("bound", "?")),
                         str(info.get("status", "?"))[:24], elapsed, "yes" if ok else "NO"))
            except Exception as e:
                print("%-4s %-30s  LOI: %s" % (m[0], m[2], str(e)[:40]))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
