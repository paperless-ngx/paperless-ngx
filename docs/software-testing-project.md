# Kế hoạch kiểm thử R08 + K01

## Phạm vi

Nhóm kiểm thử một baseline cố định của Paperless-ngx như QA độc lập. Không kiểm thử toàn bộ hệ thống; mỗi thành viên phụ trách một hàm hoặc module xác định, chạy local/CI và không tác động server công khai.

## Năm suite

| Suite | Target | Property tối thiểu |
| --- | --- | --- |
| PBT-01 Text normalization | `paperless.parsers.utils.post_process_text` | Idempotence; loại NUL; chuẩn hóa khoảng trắng nhưng giữ ranh giới dòng |
| PBT-02 Unicode search | `documents.search._query.normalize_search_text` | NFC idempotence; chuỗi Unicode tương đương cho cùng kết quả; input NFC không đổi nghĩa |
| PBT-03 Path security | `documents.file_handling.validate_path_in_root` | Path trong root hợp lệ; traversal/path ngoài root bị chặn; resolve/symlink không vượt biên |
| PBT-04 MIME-extension | `documents.parsers` | MIME hỗ trợ có extension; extension không phân biệt hoa thường; registry và supported set nhất quán |
| PBT-05 Parser selection | `ParserRegistry.get_parser_for_file` | Score cao nhất thắng; external thắng khi hòa; remote bị loại khi `allow_remote=false` |

Mỗi suite phải có ít nhất 3 property độc lập, strategy có giới hạn, shrinking, seed tái lập và counterexample tối thiểu.

## Review chéo

- Dân và Thịnh review lẫn nhau.
- Vương review Huỳnh; Huỳnh review Bo; Bo review Vương.
- Owner không tự merge khi reviewer chưa xác nhận property, bằng chứng chạy và phạm vi.

## Deliverables theo cycle

1. **Design:** invariant, strategy, precondition, oracle, giới hạn input và pass/fail.
2. **Implementation:** Hypothesis tests, dependency, lệnh chạy độc lập và CI.
3. **Evidence:** log, metrics, seed, minimized counterexample, defect/coverage và RCA.
4. **Final:** báo cáo theo Phần A-H, demo máy sạch và peer-review evidence.
