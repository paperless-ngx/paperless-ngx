# PBT-03 Cycle 4: Báo cáo tổng kết, Hướng dẫn tái lập máy sạch & Kịch bản Demo bảo vệ

## Thông tin chung & Phân công

- **Issue**: [#50 — [Cycle 4][Vương] Final report & demo PBT-03 Path security](https://github.com/0Yaam/paperless-ngx/issues/50)
- **Người thực hiện (Owner)**: Phan Khánh Vương (`@vuong123s`, MSSV `2312802`)
- **Người review chéo (Peer Reviewer)**: Phùng Nguyễn Hoài Bo (`@HubertPhung`, MSSV `2312585`)
- **Suite**: `PBT-03` — An toàn giới hạn đường dẫn (`Path Containment Security`)
- **Hàm mục tiêu (Target)**: `documents.file_handling.validate_path_in_root(path: Path, root: Path) -> None`
- **Ngoại lệ an toàn (Exception)**: `documents.file_handling.UnsafeFilePathError`
- **Baseline nhánh fork cố định**: `dev@b29fec117053637428a935d43af16d9e1d65c1fb` (và commit mở Cycle 4 `dev@0944d035255e9c6329ac74282661c9672240a5d5`)
- **Baseline upstream**: `da3de299f`
- **Tài liệu các Cycle trước**:
  - Thiết kế Cycle 1: [`pbt-03-path-security-design.md`](pbt-03-path-security-design.md)
  - PR triển khai Cycle 2: [#21](https://github.com/0Yaam/paperless-ngx/pull/21) (`20edae480`)
  - Bằng chứng & RCA Cycle 3: [`pbt-03-cycle-3-evidence.md`](pbt-03-cycle-3-evidence.md) (PR [#40](https://github.com/0Yaam/paperless-ngx/pull/40) `cb087a99b` + PR chuẩn hóa CI `#42` `2fa7b2dec`)

---

## 1. Báo cáo tổng kết PBT-03 (Chuẩn cấu trúc Phần A–H)

### Phần A — Mục tiêu hệ thống & Ngữ cảnh luồng dữ liệu

Paperless-ngx tiếp nhận tài liệu qua Web UI, REST API (`POST /api/documents/post_document/`), quy tắc email và thư mục `consume/` (`UC-01`), lập chỉ mục văn bản trong Tantivy (`UC-02`), sau đó phục vụ file gốc hoặc bản lưu trữ PDF/A qua `serve_file` (`UC-03`).

Trong quá trình lưu trữ và tiếp nhận (`documents.consumer` và `documents.file_handling`), mọi đường dẫn đích được tạo từ tên tệp, template đường dẫn lưu trữ hoặc metadata tuyệt đối không được phép vượt ra ngoài thư mục gốc cho phép (`ORIGINALS_DIR` hoặc `ARCHIVE_DIR`). Hàm `validate_path_in_root` giữ nhiệm vụ chốt chặn kiểm soát biên thư mục trước khi ghi hoặc di chuyển tập tin.

### Phần B — Kiến trúc & Cơ chế hoạt động của module kiểm thử

- **Module mục tiêu**: `src/documents/file_handling.py` (dòng `15–29`).
- **Cơ chế bảo vệ**:
  1. Phân giải cả `path` cần kiểm tra và `root` về đường dẫn vật lý chuẩn tắc (`canonical physical path`) thông qua `Path.resolve()`, loại bỏ hoàn toàn các đoạn `.` / `..` và phân giải chuỗi symbolic link.
  2. Kiểm tra quan hệ chứa theo từng thành phần thư mục bằng `Path.is_relative_to()` nhằm tránh lỗi nhầm lẫn tiền tố chuỗi (`prefix confusion`).
  3. Ghi log cảnh báo qua `paperless.filehandling` và ném ngoại lệ `UnsafeFilePathError` nếu đường dẫn rơi ra ngoài `root`.

### Phần C — Môi trường & Baseline đã kiểm chứng

- **Baseline nhánh fork cố định**: `dev@b29fec117053637428a935d43af16d9e1d65c1fb` (đồng thời đã chạy kiểm chứng trên `dev@0944d0352`).
- **Phiên bản phụ thuộc khóa cứng (`uv.lock`)**: `Python 3.12` (CI) / `3.13.5` (máy cục bộ `.temp_test_venv`), `pytest 9.1.1`, `hypothesis 6.168.5`, `pytest-cov 7.1.0`, `pytest-django 4.14.0`, `coverage.py 7.17.2`.
- **Cấu hình hạt giống & Profile tất định**: `HYPOTHESIS_PROFILE=recorded` (`max_examples=250`, `deadline=None`, `suppress_health_check=[HealthCheck.function_scoped_fixture]`), `--hypothesis-seed=20261008`, `--cov=documents.file_handling --cov-branch`, `-n 0`.
- **Kết quả GitHub Actions CI xác thực**: [Coursework CI Run #45791632304](https://github.com/0Yaam/paperless-ngx/actions/runs/45791632304) (`dev@0944d0352`, `2026-11-26T09:24:16Z -> 09:25:00Z`, job `PBT-03 path security` — **success** trong `44s`).

### Phần D — Cơ sở kỹ thuật K01 PBT, Phạm vi, Giả định & Tiêu chí Pass/Fail

- **Lý do áp dụng PBT cho `validate_path_in_root`**: Bài toán kiểm soát đường dẫn có tổ hợp đầu vào rất lớn gồm độ sâu thư mục lồng nhau, các tiền tố dễ gây nhầm lẫn (`storage_root_rogue`), chuỗi nhảy cấp `..` nhiều tầng và đích trỏ của symlink qua nhiều hệ điều hành — những tình huống mà vài ca kiểm thử thủ công dễ bỏ sót.
- **Giả định & Giới hạn phạm vi**:
  - Bộ sinh tên thành phần đường dẫn ASCII an toàn (`_SAFE_COMPONENT_STRATEGY`, độ dài `1..20`, có tiền tố `p_`) bảo đảm tính tương thích giữa Windows và Linux.
  - Quyền phân quyền hệ điều hành (ACL) và điều kiện tranh chấp TOCTOU nằm ngoài phạm vi của `pathlib.Path.resolve()`.
  - Hai property kiểm tra symlink (`PBT03-INV3A/B`) chỉ gọi `pytest.skip` trên máy không cho phép tạo symlink (Windows chưa bật Developer Mode/quyền Admin); trên Ubuntu CI và Windows đã bật Developer Mode, toàn bộ 500 ca symlink đều chạy trực tiếp.
- **Tiêu chí Pass/Fail**:
  - **PASS**: Toàn bộ 5 property hoàn thành `max_examples=250` với `0` lỗi assertion, ném đúng `UnsafeFilePathError` cho mọi đường dẫn ngoài root và đạt `0` partial branch trên `validate_path_in_root`.
  - **FAIL**: Bất kỳ đầu vào hợp lệ nào làm sập chương trình ngoài ý muốn hoặc vượt qua `validate_path_in_root` mà không ném `UnsafeFilePathError` khi ở ngoài `root`.

### Phần E — Thiết kế kiểm thử, Bất biến & Các ca biên `@example`

Bộ test `src/documents/tests/test_path_security.py` cài đặt **5 property độc lập** kèm **8 ca biên tường minh (`@example`)**:

| ID          | Hàm kiểm thử                                  | Bất biến (`Invariant`)                                                           | Chiến lược sinh (`Strategy`)                                                | Oracle & Ca biên (`@example`)                                                                              |
| :---------- | :-------------------------------------------- | :------------------------------------------------------------------------------- | :-------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------- |
| PBT03-INV1  | `test_descendants_inside_root_accepted`       | Mọi đường dẫn con hợp lệ nằm trong `root` đều được chấp nhận.                    | `st.lists(_SAFE_COMPONENT_STRATEGY, min_size=1, max_size=5)`                | Hàm trả về bình thường; `target.resolve().is_relative_to(root.resolve())`. Ví dụ: `["p_single_file.pdf"]`. |
| PBT03-INV2A | `test_traversal_outside_root_rejected`        | Mọi đường dẫn dùng `..` thoát khỏi `root` đều bị chặn.                           | `prefix` (0–5) + `[".."] * (len(prefix) + extra_depth)` (1–8) + `filename`. | Ném `UnsafeFilePathError`; đích resolve ngoài `root`. Ví dụ: `([], 1, "p_passwd")`.                        |
| PBT03-INV2B | `test_prefix_confusion_outside_root_rejected` | Thư mục anh em `storage_root_<suffix>` trùng tiền tố chuỗi vẫn bị coi là ngoài.  | `sibling_suffix` (`_SAFE_COMPONENT_STRATEGY`) + 1–4 thành phần.             | Ném `UnsafeFilePathError`. Ví dụ: `("rogue", ["p_secret.pdf"])`, `("_backup", ["p_sub", "p_file.png"])`.   |
| PBT03-INV3A | `test_symlink_escaping_root_rejected`         | Symlink đặt trong `root` nhưng trỏ ra tệp bên ngoài `root` bị chặn khi resolve.  | Tệp mật trong `tmp_path/outside/`, symlink đặt trong `root/`.               | Ném `UnsafeFilePathError`. Ví dụ: `"p_sensitive_outside.txt"`.                                             |
| PBT03-INV3B | `test_symlink_internal_to_root_accepted`      | Symlink đặt trong `root` trỏ tới tệp nội bộ trong `root` được chấp nhận an toàn. | Tệp đích nằm trong `root/`, symlink đặt trong `root/`.                      | Hàm trả về bình thường; symlink resolve thuộc `root`. Ví dụ: `"p_internal_target.txt"`.                    |

### Phần F — Cấu trúc Harness tự động & Tích hợp CI

- **Mã nguồn kiểm thử**: `src/documents/tests/test_path_security.py` (khai báo tập trung 4 profile `dev`, `ci`, `recorded`, `stress` điều khiển qua biến `HYPOTHESIS_PROFILE`).
- **Script kiểm chứng máy sạch**: [`scripts/demo-pbt-03.sh`](../scripts/demo-pbt-03.sh) kiểm tra baseline `b29fec117053637428a935d43af16d9e1d65c1fb`, kiểm tra không có sửa đổi mã nguồn mục tiêu hay sửa đổi chưa commit, đồng bộ phụ thuộc khóa cứng, chạy tất định PBT-03 với branch coverage và tự động xác minh kết quả qua `verification.json` + SHA-256 log.
- **Cấu hình CI**: Job `pbt-03` trong [`.github/workflows/coursework-ci.yml`](../.github/workflows/coursework-ci.yml#L125) gọi trực tiếp `bash scripts/demo-pbt-03.sh` trên `ubuntu-latest` Python `3.12` (`fetch-depth: 0`, `PBT03_ARTIFACT_DIR: .artifacts`) và tải lên gói artifact `pbt-03-evidence` (`.artifacts/`).

### Phần G — Số liệu Cycle 3, Kết quả đo từ Checkout sạch & Phân tích RCA

1. **Thống kê kiểm chứng trên Checkout sạch (`dev@b29fec117`, detached worktree ngày `26/11/2026`)**:
   Chạy lại bộ kiểm thử từ thư mục checkout mới hoàn toàn tại commit `b29fec117053637428a935d43af16d9e1d65c1fb` đạt **5/5 PASSED trong 13.56s** (`1,250` ca sinh hợp lệ + `8` ca `@example`, `0` lỗi):

   | Property                                      | Passed | Failed | Invalid (Trùng lặp) | Pha sinh (`generate`) | Thời gian gọi hàm |
   | :-------------------------------------------- | -----: | -----: | ------------------: | --------------------: | ----------------: |
   | `test_descendants_inside_root_accepted`       |    250 |      0 |                  43 |                1.43 s |            2.94 s |
   | `test_traversal_outside_root_rejected`        |    250 |      0 |                  25 |                1.74 s |            1.76 s |
   | `test_prefix_confusion_outside_root_rejected` |    250 |      0 |                  35 |                2.67 s |            2.70 s |
   | `test_symlink_escaping_root_rejected`         |    250 |      0 |                   0 |                1.52 s |            1.53 s |
   | `test_symlink_internal_to_root_accepted`      |    250 |      0 |                   0 |                1.18 s |            1.20 s |
   | **Tổng cộng (`PBT-03`)**                      |  1,250 |      0 |                 103 |                8.54 s |           13.56 s |

   _(Số ca `103` Invalid (< 7.6%) phát sinh do cơ chế khử trùng lặp nội bộ của Hypothesis khi sinh `st.lists`/`st.text`; bộ test không sử dụng `.filter()` hay `assume()`. Bản ghi chi tiết Cycle 3 trước đó tại [`pbt-03-cycle-3-evidence.md`](pbt-03-cycle-3-evidence.md) cũng cho kết quả tương đương: `1,250 passed`, `103 invalid`, tổng thời gian `10.54s`.)_

2. **Bằng chứng bao phủ nhánh tất định (`coverage.py --branch`)**:

   ```text
   Name                             Stmts   Miss Branch BrPart  Cover   Missing
   ----------------------------------------------------------------------------
   src\documents\file_handling.py      96     76     44      0    16%   33, 37-62, 77-122, 126-153, 164-216
   ----------------------------------------------------------------------------
   ```

   - **Hàm mục tiêu `validate_path_in_root` (`dòng 21–29`) & `UnsafeFilePathError` (`dòng 15–18`)**: Đạt **100% Statement Coverage (10/10 dòng)** và **100% Branch Coverage** (`0` dòng thiếu trong vùng `15–30`, `BrPart = 0`). Cả hai nhánh `True` (từ chối, ghi log, ném ngoại lệ) và `False` (chấp nhận đường dẫn hợp lệ) đều đã được kích hoạt đầy đủ. Các dòng `Missing` (`33`, `37–62`, `77–216`) thuộc các hàm phụ trợ khác nằm ngoài phạm vi target `validate_path_in_root`.

3. **Kiểm chứng cơ chế Shrinking & Phát hiện phòng thủ chiều sâu (RCA)** (trích từ [`pbt-03-cycle-3-evidence.md`](pbt-03-cycle-3-evidence.md)):
   - **Thí nghiệm giả lập lỗi & Shrinking**: Khi bỏ `.resolve()` trong phiên bản giả lập khuyết thiếu (`if not path.is_relative_to(root):`), kiểm thử `test_symlink_escaping_root_rejected` lập tức thất bại (`DID NOT RAISE UnsafeFilePathError`) và Hypothesis tự co gọn về ví dụ phản chứng tối thiểu **`filename='p_0'`**.
   - **Phát hiện phòng thủ chiều sâu (`delete_empty_directories`)**: Khi rà soát toàn tệp `src/documents/file_handling.py`, nhóm phát hiện hàm dọn thư mục rỗng `delete_empty_directories(directory, root)` (`dòng 36–62`) kiểm tra `if not directory.is_relative_to(root):` theo cú pháp **mà không gọi `.resolve()`**. Nếu tồn tại symlink bên trong `root` trỏ ra thư mục ngoài `root`, thao tác xóa cha đệ quy có nguy cơ leo ra khỏi ranh giới cho phép. Khuyến nghị: chuẩn hóa bằng `directory.resolve().is_relative_to(root.resolve())` hoặc gọi trực tiếp `validate_path_in_root(directory, root)`.

### Phần H — Lưu cứng phiên bản & Danh mục truy vết

| Thành phần / Mốc đối chiếu       | Mã định danh / Commit / Run                         | Ý nghĩa                                                 |
| :------------------------------- | :-------------------------------------------------- | :------------------------------------------------------ |
| Baseline nhánh fork cố định      | `dev@b29fec117053637428a935d43af16d9e1d65c1fb`      | Mốc checkout sạch dùng để kiểm chứng tái lập            |
| Commit mở Cycle 4                | `dev@0944d035255e9c6329ac74282661c9672240a5d5`      | Cập nhật trạng thái Cycle 4 & lệnh tái lập trong README |
| Kết quả Coursework CI trên `dev` | Run `#45791632304` (`PBT-03 path security` — `44s`) | Lần chạy chuẩn trên Ubuntu Python 3.12 & tạo artifact   |
| Tệp artifact log CI              | `pbt-03-evidence` (`.artifacts/pbt-03-run.log`)     | Toàn bộ stdout pytest, branch coverage, Hypothesis stat |
| Mã nguồn bộ kiểm thử             | `src/documents/tests/test_path_security.py`         | Bộ test Hypothesis tự động                              |

---

## 2. Hướng dẫn tái lập trên máy sạch (Clean-Machine Reproduction)

### Điều kiện tiên quyết

- Git (`>= 2.40`)
- Astral `uv` (`0.12.x`) + Python `3.12` (trên Linux / macOS / WSL2 / Docker để tương thích trọn vẹn với `uv.lock`)

### Các bước chạy lại trên máy mới (Linux / macOS / WSL2)

```bash
# 1. Clone mới repository (lịch sử đầy đủ để đối chiếu baseline)
git clone https://github.com/0Yaam/paperless-ngx.git
cd paperless-ngx

# 2. Chạy script tái lập máy sạch chuẩn hóa cho PBT-03
bash scripts/demo-pbt-03.sh
```

Script [`scripts/demo-pbt-03.sh`](../scripts/demo-pbt-03.sh) tự động thực hiện tuần tự: kiểm tra `git`/`uv` và lịch sử `baseline` (`b29fec117053637428a935d43af16d9e1d65c1fb`), xác minh không có trôi mã nguồn hay sửa đổi chưa commit, đồng bộ môi trường bằng `uv sync --python 3.12 --group testing --frozen`, chạy `pytest` tất định với `HYPOTHESIS_PROFILE=recorded` và `--hypothesis-seed=20261008 --cov=documents.file_handling --cov-branch`, xuất báo cáo JSON và xác minh tự động `5/5` property + `100%` độ bao phủ hàm mục tiêu. Toàn bộ bằng chứng (`environment.txt`, `pbt-03-run.log`, `coverage.json`, `verification.json`) được lưu tại `.artifacts/pbt-03-cycle-4/`.

Khi cần chạy thủ công từng bước tách rời:

```bash
uv sync --python 3.12 --group testing --frozen
HYPOTHESIS_PROFILE=recorded uv run --python 3.12 --dev --frozen pytest \
  src/documents/tests/test_path_security.py -k TestPathSecurity -n 0 -v \
  --hypothesis-seed=20261008 --hypothesis-show-statistics \
  --cov=documents.file_handling --cov-branch --cov-report=term-missing
```

### Chạy trên Windows (PowerShell với venv đã đồng bộ sẵn)

Do `uv.lock` giới hạn một số wheel chỉ dành cho Linux/macOS (`sys_platform`), trên Windows dùng thư mục checkout tách biệt kết hợp venv kiểm thử đã cài:

```powershell
git worktree add --detach ../paperless-pbt03-clean b29fec117053637428a935d43af16d9e1d65c1fb
Push-Location ../paperless-pbt03-clean
$env:PYTHONPATH = (Resolve-Path "src").Path
$env:DJANGO_SETTINGS_MODULE = "paperless.settings"
$env:PAPERLESS_SECRET_KEY = "test-secret-key-for-pbt-tests"
$env:HYPOTHESIS_PROFILE = "recorded"

# Chạy tất định với seed 20261008 và đo branch coverage
python -m coverage run --branch --source=documents.file_handling `
  -m pytest --no-cov src/documents/tests/test_path_security.py -k TestPathSecurity `
  -n 0 -v --hypothesis-seed=20261008 --hypothesis-show-statistics
python -m coverage report -m
Pop-Location
```

### Đầu ra & Thống kê kỳ vọng

- **Kết quả Pytest**: `5 passed` (`100%`)
- **Thống kê Hypothesis**: Mỗi hàm test đạt `250 passing, 0 failing` (tổng `1,250` ca sinh hợp lệ + `8` ca `@example`); số ca invalid deduplicated lần lượt là `43 / 25 / 35 / 0 / 0`.
- **Branch Coverage**: `BrPart = 0`, không có dòng nào trong khoảng `15–29` (`UnsafeFilePathError` và `validate_path_in_root`) xuất hiện tại cột `Missing`.
- **Tệp xác minh tự động**: `verification.json` in ra JSON đạt ngưỡng kèm mã băm `log_sha256` của tệp `pbt-03-run.log`.
- **Artifact trên GitHub Actions**: Tải gói `pbt-03-evidence` (chứa `environment.txt`, `pbt-03-run.log`, `coverage.json`, `verification.json`) trong workflow **Coursework CI** $\rightarrow$ job **PBT-03 path security**.

---

## 3. Kịch bản Demo bảo vệ cuối kỳ (3–5 phút)

Thực hiện tuần tự 4 bước sau tại buổi bảo vệ mà không cần bước cài đặt ngầm nào khác:

1. **Kiểm tra trạng thái trước khi chạy (30 giây)**:
   Xác nhận đúng commit trên nhánh `dev` và lịch sử baseline:

   ```bash
   git rev-parse --short HEAD   # Kỳ vọng: b29fec117 hoặc commit merge mới nhất trên dev
   ```

2. **Chạy trực tiếp script demo tự động cả 4 nhóm tình huống an ninh + đo Branch Coverage (90 giây)**:
   Chạy câu lệnh duy nhất:

   ```bash
   bash scripts/demo-pbt-03.sh
   ```

   Giải thích 5 kết quả in ra màn hình cho Hội đồng:
   - **Đường dẫn hợp lệ trong root (`Descendant`)**: `test_descendants_inside_root_accepted`
   - **Tấn công vượt thư mục (`Traversal`)**: `test_traversal_outside_root_rejected` (chặn chuỗi `..`)
   - **Nhầm lẫn tiền tố (`Prefix Confusion`)**: `test_prefix_confusion_outside_root_rejected` (chặn thư mục anh em `storage_root_<suffix>`)
   - **Liên kết tượng trưng (`Symlinks`)**: `test_symlink_escaping_root_rejected` (chặn symlink trỏ ra ngoài) & `test_symlink_internal_to_root_accepted` (cho phép symlink nội bộ)
   - **Bảng Coverage**: Chỉ rõ `BrPart = 0` và dòng `Missing` bắt đầu từ `33` (`100%` statement/branch coverage cho dòng `21–29`).

3. **Minh họa cơ chế Shrinking khi bỏ `.resolve()` (60 giây — tùy chọn)**:
   Chạy nhanh đoạn kiểm chứng trong bộ nhớ (không sửa file đang theo dõi trong Git) để minh họa vì sao bắt buộc phải dùng `.resolve()`:

   ```python
   # Minh họa lỗi giả lập: bỏ .resolve() làm fail test symlink escaping và tự shrink về 'p_0'
   # Kết quả kỳ vọng: Failed: DID NOT RAISE UnsafeFilePathError
   # Falsifying example: filename='p_0'
   ```

   Kết nối sang phát hiện bảo mật chiều sâu ở hàm `delete_empty_directories` (`dòng 40`) đã trình bày tại [`pbt-03-cycle-3-evidence.md`](pbt-03-cycle-3-evidence.md).

4. **Phương án dự phòng nếu gặp sự cố môi trường khi Demo**:
   - **Tình huống A (Windows chưa bật quyền tạo symlink)**: Hai test symlink `PBT03-INV3A/B` sẽ chủ động báo `SKIPPED` qua `pytest.skip` chứ không báo `PASSED` giả; khi đó chuyển sang WSL2/Ubuntu hoặc mở kết quả chạy Ubuntu trên GitHub Actions.
   - **Tình huống B (Mất mạng hoặc lỗi CI tạm thời)**: Mở trực tiếp tệp log đã tải sẵn `.artifacts/pbt-03-run.log` từ [Run #45791632304](https://github.com/0Yaam/paperless-ngx/actions/runs/45791632304) kèm log checkout sạch ở trên.

---

## 4. Bằng chứng Review chéo (Peer-Review Evidence)

| Giai đoạn  | Pull Request / Issue                                          | Người review   | Nội dung góp ý & Chỉnh sửa                                                                                                                                                                                      | Kết quả & Commit                                              |
| :--------- | :------------------------------------------------------------ | :------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------ |
| Cycle 1–2  | [PR #21](https://github.com/0Yaam/paperless-ngx/pull/21)      | `@HubertPhung` | Yêu cầu tách riêng property traversal và prefix confusion, chuyển kiểm tra symlink thành property Hypothesis, bỏ `django_db` thừa và bổ sung tài liệu thiết kế. Đã chỉnh sửa đầy đủ.                            | Đã merge `20edae480`                                          |
| Cycle 3    | [PR #40](https://github.com/0Yaam/paperless-ngx/pull/40)      | `@HubertPhung` | Xác nhận 5/5 pass, 100% coverage & phát hiện RCA `delete_empty_directories`; yêu cầu sửa `codespell`, chạy `prettier`, sửa anchor, bỏ lặp `register_profile`, thêm ví dụ shrink. Sửa ở `7905814bc`–`10747a862`. | **`APPROVED`** (`2026-11-24T07:55:23Z`), Đã merge `cb087a99b` |
| Cycle 3 CI | [PR #42](https://github.com/0Yaam/paperless-ngx/pull/42)      | `@0Yaam`       | Bổ sung `-n 0` và `--cov-branch` cho job `pbt-03` trong `coursework-ci.yml` để cố định thứ tự log và đo độ bao phủ nhánh.                                                                                       | Đã merge `2fa7b2dec`                                          |
| Cycle 4    | Issue [#50](https://github.com/0Yaam/paperless-ngx/issues/50) | `@HubertPhung` | Tổng hợp báo cáo chuẩn A–H, kiểm chứng checkout sạch tại `b29fec117`, hoàn thiện kịch bản demo bảo vệ và bảng truy vết review.                                                                                  | Đang chờ review & approve cuối trên PR                        |
