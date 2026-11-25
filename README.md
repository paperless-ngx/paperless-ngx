# R08 Paperless-ngx · K01 Property-Based Testing

Đồ án môn **Kiểm thử phần mềm** trên mã nguồn [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx), áp dụng **K01 — Property-Based Testing**.

- **Project:** https://github.com/users/0Yaam/projects/2
- **Cycle đang mở:** Cycle 2 — Implement Property Suites; việc thiết kế chưa xong được chuyển tiếp từ Cycle 1.
- **Baseline upstream:** `da3de299f`
- **Mục tiêu:** 5 suite độc lập, mỗi suite tối thiểu 3 property; tổng tối thiểu 15 property.

## Nhóm

| Thành viên             | GitHub                                               | Suite K01                 | Reviewer |
| ---------------------- | ---------------------------------------------------- | ------------------------- | -------- |
| Nguyễn Ngọc Trường Dân | [@0Yaam](https://github.com/0Yaam)                   | PBT-01 Text normalization | Thịnh    |
| Nguyễn Hưng Thịnh      | [@elgthinhnguyen](https://github.com/elgthinhnguyen) | PBT-02 Unicode search     | Dân      |
| Phan Khánh Vương       | [@vuong123s](https://github.com/vuong123s)           | PBT-03 Path security      | Bo       |
| Vũ Thế Huỳnh           | [@1convitt](https://github.com/1convitt)             | PBT-04 MIME-extension     | Vương    |
| Phùng Nguyễn Hoài Bo   | [@HubertPhung](https://github.com/HubertPhung)       | PBT-05 Parser selection   | Huỳnh    |

## Kế hoạch

| Cycle | Nội dung                                               | Trạng thái  |
| ----- | ------------------------------------------------------ | ----------- |
| 1     | Chốt invariant, strategy, oracle và tiêu chí pass/fail | Đã chốt     |
| 2     | Viết Hypothesis tests và lệnh chạy độc lập             | **Đang mở** |
| 3     | Chạy test, lưu counterexample, metrics, defect và RCA  | Backlog     |
| 4     | Báo cáo, demo tái lập và peer review                   | Backlog     |

## Quy trình

Tái lập PBT-01/02/03 với seed cố định (Linux/macOS hoặc CI):

```bash
uv sync --python 3.12 --group testing --frozen
uv run --python 3.12 --dev --frozen pytest src/paperless/tests/test_parser_utils.py -k TestPostProcessText --hypothesis-seed=20261008
uv run --python 3.12 --dev --frozen pytest src/documents/tests/search/test_unicode_normalization.py -k TestTheNormalizer --hypothesis-seed=20261008
HYPOTHESIS_PROFILE=recorded uv run --python 3.12 --dev --frozen pytest src/documents/tests/test_path_security.py -k TestPathSecurity -v --hypothesis-seed=20261008 --hypothesis-show-statistics --cov=documents.file_handling --cov-report=term-missing
```

1. Nhận việc từ Project, chuyển `Stage` sang `In Progress`.
2. Tạo branch từ `dev`; mỗi PR xử lý đúng một issue.
3. Chạy test hẹp nhất liên quan và đính kèm seed/counterexample/log.
4. Reviewer chéo duyệt trước khi squash merge.

Chi tiết phạm vi và tiêu chí: [`docs/software-testing-project.md`](docs/software-testing-project.md). Hướng dẫn Paperless-ngx gốc: https://docs.paperless-ngx.com.
