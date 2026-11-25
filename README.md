# Class - Course - Teacher Assignment and TimeTabling (OR-Tools)

Giải bài toán phân công giáo viên và xếp thời khóa biểu cho các lớp-môn bằng nhiều phương pháp:
Constraint Programming, Integer Programming, Linear Programming và quay lui.

- Mô hình hóa chi tiết: `modeling/modeling.docx`
- Kết quả so sánh các phương pháp: `compare/compare.docx`

## Cài đặt

    pip install ortools

Đã thử với Python 3.13, OR-Tools 9.15.

## Cấu trúc

| File | Nội dung |
| --- | --- |
| `common.py` | đọc input, tiền xử lý (lớp-môn, T_c, U_c, cặp xung đột), greedy, kiểm tra, ghi output |
| `s1_cpsat_interval.py` | CP-SAT, biến khoảng + NoOverlap (khuyên dùng) |
| `s2_cpsat_csp.py` | CP-SAT, CSP biến nguyên + ràng buộc tuyển theo cặp |
| `s3_cp_classic.py` | CP solver cổ điển (pywrapcp), lan truyền + cây tìm kiếm |
| `s4_mip_time_indexed.py` | quy hoạch nguyên, công thức time-indexed |
| `s5_mip_bigm.py` | quy hoạch nguyên, công thức big-M |
| `s6_lp_relaxation.py` | nới lỏng LP (GLOP) + làm tròn / diving |
| `s7_branch_and_bound_lp.py` | nhánh cận tự cài, LP tại mỗi nút |
| `s8_backtracking.py` | quay lui thuần Python |
| `checker.py` | kiểm tra tính hợp lệ của output |
| `run_all.py` | chạy nhiều phương pháp, in bảng so sánh |
| `gen.py` | sinh instance ngẫu nhiên |
| `tests/` | ví dụ đề bài và 8 instance thử |

## Chạy một solver

    python <solver>.py <input> [-o OUTPUT] [-t TIME] [--rule RULE] [-q] [cờ riêng]

Ví dụ:

    python s1_cpsat_interval.py tests/example.txt -t 30 -o out.txt
    python checker.py tests/example.txt out.txt

Output đúng định dạng đề bài được ghi ra stdout (hoặc file `-o`); thông tin trạng thái, cận trên, thời gian ghi ra stderr.

### Cờ chung (mọi solver)

| Cờ | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `input` | | file input; `-` để đọc từ stdin |
| `-o`, `--output` | stdout | file output |
| `-t`, `--time` | 30 (s1, s2, s3, s8), 60 (s4–s7) | giới hạn thời gian (giây) |
| `--rule` | `session` | quy tắc kíp hợp lệ: `session` = lớp-môn nằm trọn 1 buổi, `day` = trọn 1 ngày, `week` = chỉ cần nằm trong 60 kíp |
| `-q`, `--quiet` | tắt | không in dòng tổng kết ra stderr |

### Cờ riêng

| Solver | Cờ | Ý nghĩa |
| --- | --- | --- |
| s1, s2 | `--workers N` | số luồng tìm kiếm của CP-SAT (mặc định 8) |
| s1, s2 | `--no-hint` | không dùng lời giải greedy làm gợi ý ban đầu |
| s1, s2 | `--no-redundant` | tắt ràng buộc dư thừa (và ràng buộc kênh ở s2) |
| s4, s5 | `--solver {SCIP,CBC,SAT}` | backend MIP (mặc định SCIP) |
| s4, s5 | `--no-hint` | không dùng lời giải greedy làm MIP start |
| s5 | `--cuts` | thêm bất đẳng thức hợp lệ (cutting planes) |
| s6 | `--mode {dive,round}` | cách lấy lời giải nguyên từ LP (mặc định `dive`) |
| s6 | `--duals` | in phân tích giá trị đối ngẫu theo lớp / giáo viên |
| s7 | `--max-nodes N` | số nút tối đa của cây nhánh cận (mặc định 1 000 000) |
| s8 | `--no-symmetry` | tắt phá đối xứng giữa các buổi |

## Kiểm tra output

    python checker.py <input> <output> [--rule RULE]

In `OK  K = ...` nếu hợp lệ, ngược lại liệt kê lỗi (lớp-môn không tồn tại, giáo viên không dạy được môn, kíp không hợp lệ, chồng lấp theo lớp / giáo viên).

## So sánh các phương pháp

    python run_all.py <input...> [-t TIME] [--rule RULE] [--only LIST] [--fast] [--ablation]

| Cờ | Ý nghĩa |
| --- | --- |
| `-t` | giới hạn thời gian cho mỗi phương pháp (mặc định 30) |
| `--only s1,s4,s6` | chỉ chạy các phương pháp liệt kê (mã: s1, s2, s3, s4, s5, s5c, s6, s7, s8) |
| `--fast` | bỏ các phương pháp chỉ phù hợp instance nhỏ (s2, s3, s5, s5c, s7, s8) |
| `--ablation` | chạy thêm biến thể tắt kỹ thuật: s1-, s2- (không dư thừa), s6r (rounding), s8- (không phá đối xứng) |

Ví dụ:

    python run_all.py tests/tiny_1.txt tests/small_2.txt -t 10 --ablation
    python run_all.py tests/large_1.txt -t 60 --fast

## Sinh instance

    python gen.py T N M [--seed S] [--min-sub A] [--max-sub B] [--teach-min C] [--teach-max D] [--dmin E] [--dmax F] > input.txt

| Cờ | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `--seed` | 1 | hạt giống ngẫu nhiên |
| `--min-sub`, `--max-sub` | 2, 6 | số môn mỗi lớp |
| `--teach-min`, `--teach-max` | 1, 4 | số môn mỗi giáo viên dạy được |
| `--dmin`, `--dmax` | 2, 4 | số tiết mỗi môn |
