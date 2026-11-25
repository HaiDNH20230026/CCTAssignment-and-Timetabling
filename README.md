# Class - Course - Teacher Assignment and TimeTabling (OR-Tools)

Giải bài toán số 8 của mini-project bằng nhiều phương pháp trong phạm vi môn học.
Mô hình hoá chi tiết (ký hiệu, công thức, chứng minh, kết quả thực nghiệm) nằm trong file modeling (Claude Docs):
https://claude.ai/artifact/25Aesbmo42BXEWLWMUYoYF

## Cài đặt

    pip install ortools        # đã thử với OR-Tools 9.15, Python 3.13

## Các file

| File | Phương pháp | Tuần |
| --- | --- | --- |
| `common.py` | đọc input, tiền xử lý (lớp-môn, T_c, U_c, Q_lop, Q_gv), greedy, kiểm tra, ghi output | |
| `s1_cpsat_interval.py` | CP-SAT, biến khoảng + NoOverlap + ràng buộc dư thừa (**khuyên dùng**) | 10 |
| `s2_cpsat_csp.py` | CP-SAT, CSP biến nguyên x_c, g_c + ràng buộc "hoặc" từng cặp | 06, 10 |
| `s3_cp_classic.py` | CP solver cổ điển (pywrapcp): lan truyền + cây tìm kiếm first-fail | 10 |
| `s4_mip_time_indexed.py` | IP time-indexed x[c,t,u], SCIP/CBC/SAT | 08-09 |
| `s5_mip_bigm.py` | IP big-M (either-or), tuỳ chọn `--cuts` (cutting planes) | 08-09 |
| `s6_lp_relaxation.py` | LP relaxation (GLOP) + rounding / diving, cận trên, `--duals` | 04-05 |
| `s7_branch_and_bound_lp.py` | Branch & Bound tự cài, LP ở mỗi nút (GLOP) | 08-09 |
| `s8_backtracking.py` | Backtracking TRY(k) thuần Python + phá đối xứng | 06 |
| `checker.py` | kiểm tra output | |
| `run_all.py` | chạy nhiều phương pháp, in bảng so sánh | |
| `gen.py` | sinh instance ngẫu nhiên | |

## Chạy

    python s1_cpsat_interval.py tests/example.txt -t 30 -o out.txt
    python checker.py tests/example.txt out.txt

    python run_all.py tests/small_2.txt -t 10 --ablation
    python run_all.py tests/large_1.txt -t 60 --fast

Output (đúng định dạng đề bài) in ra stdout; log (status, cận trên, thời gian) in ra stderr.

## Giả thiết

Mỗi lớp-môn học liền d(m) tiết và nằm trọn trong 1 buổi (6 tiết) — khớp với output mẫu.
Đổi bằng `--rule day` (trọn 1 ngày) hoặc `--rule week` (chỉ cần trong 60 kíp).
