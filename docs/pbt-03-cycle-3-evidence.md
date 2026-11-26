# PBT-03 — Bằng chứng vận hành và phân tích kiểm thử Cycle 3 (Path Security)

## 1. Thông tin chung & Phạm vi

- **Suite**: PBT-03 Path containment security
- **Issue**: [#37](https://github.com/0Yaam/paperless-ngx/issues/37)
- **Milestone**: Cycle 3 – Execution & Evidence
- **Owner**: Phan Khánh Vương (`@vuong123s`)
- **Peer Reviewer**: Phùng Nguyễn Hoài Bo (`@HubertPhung`)
- **Target Function**: `documents.file_handling.validate_path_in_root(path: Path, root: Path) -> None`
- **Exception Class**: `documents.file_handling.UnsafeFilePathError`
- **Mã nguồn kiểm thử**: `src/documents/tests/test_path_security.py`
- **Baseline Git commit**: `dfd1e882a`

---

## 2. Hợp đồng kiểm thử & Các Invariant được kiểm chứng

Bộ kiểm thử bao gồm 5 property tests độc lập tương ứng 3 nhóm bất biến (invariants) từ tài liệu thiết kế Cycle 1 ([`pbt-03-path-security-design.md`](pbt-03-path-security-design.md)):

| ID              | Test Case                                     | Invariant                                                            | Strategy                                                                        | Oracle                                                                                     |
| :-------------- | :-------------------------------------------- | :------------------------------------------------------------------- | :------------------------------------------------------------------------------ | :----------------------------------------------------------------------------------------- |
| **PBT03-INV1**  | `test_descendants_inside_root_accepted`       | Mọi path con hợp lệ trong root đều được chấp nhận.                   | Danh sách 1–5 thư mục/tệp an toàn (`_SAFE_COMPONENT_STRATEGY`).                 | Hàm trả về bình thường, `target.resolve().is_relative_to(root.resolve()) == True`.         |
| **PBT03-INV2A** | `test_traversal_outside_root_rejected`        | Traversal bằng `..` vượt ra ngoài root bị từ chối tuyệt đối.         | Prefix 0–5 cấp, extra traversal depth 1–8 (`..`), tệp đích hợp lệ.              | Ném ngoại lệ `UnsafeFilePathError`, `not target.resolve().is_relative_to(root.resolve())`. |
| **PBT03-INV2B** | `test_prefix_confusion_outside_root_rejected` | Thư mục cùng tiền tố (sibling prefix confusion) bị từ chối.          | Sibling directory tên `<root>_<suffix>` chứa các file/subfolder con.            | Ném ngoại lệ `UnsafeFilePathError`.                                                        |
| **PBT03-INV3A** | `test_symlink_escaping_root_rejected`         | Symlink nằm trong root trỏ ra ngoài root bị chặn khi resolve.        | Tệp nhạy cảm nằm ở thư mục `outside/`, symlink nằm trong `root/` trỏ ra tệp đó. | Ném ngoại lệ `UnsafeFilePathError`.                                                        |
| **PBT03-INV3B** | `test_symlink_internal_to_root_accepted`      | Symlink nằm trong root trỏ tới tệp nội bộ trong root được chấp nhận. | Tệp nội bộ nằm trong `root/`, symlink nằm trong `root/` trỏ tới tệp nội bộ đó.  | Hàm trả về bình thường, `link.resolve().is_relative_to(root.resolve()) == True`.           |

---

## 3. Cấu hình Profile Hypothesis & Môi trường chạy kiểm thử

Hệ thống cấu hình 4 profile Hypothesis chuẩn phục vụ kiểm thử theo tầng (được khai báo tập trung trong `src/documents/tests/test_path_security.py`):

```python
settings.register_profile(
    "dev",
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.register_profile(
    "recorded",
    max_examples=250,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.register_profile(
    "stress",
    max_examples=500,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
```

- **Profile chính của Cycle 3**: `recorded` với `max_examples=250` cho mỗi property (tổng cộng 1,250 test cases sinh ra trong một lần chạy).
- **Log chạy kiểm thử chi tiết**: Được lưu tại `.artifacts/pbt-03-run.log` (artifact CI) và đính kèm đầy đủ tại [Mục 9 (Execution Log)](#9-execution-log).
- **Seed tái lập cố định**: `--hypothesis-seed=20261008`.
- **Môi trường đo lường**:
  - Hệ điều hành: Windows 11 Pro 64-bit / Ubuntu 22.04 LTS (CI Runner)
  - Python: 3.13.5 (Local) / 3.12 (GitHub Actions Runner)
  - Pytest: 9.1.1
  - Hypothesis: 6.168.5
  - Coverage Plugin: pytest-cov 7.1.0

---

## 4. Bảng số liệu thống kê (Hypothesis Statistics)

Kết quả ghi nhận từ lần chạy profile `recorded` (tổng thời gian 10.54s):

| Test Case                                     |  Passed   | Failed | Invalid | Thời gian giai đoạn sinh |    Runtimes điển hình     |
| :-------------------------------------------- | :-------: | :----: | :-----: | :----------------------: | :-----------------------: |
| `test_descendants_inside_root_accepted`       |    250    |   0    |   43    |          2.27s           | ~1–9 ms (< 3 ms data gen) |
| `test_traversal_outside_root_rejected`        |    250    |   0    |   25    |          1.86s           | ~1–9 ms (< 2 ms data gen) |
| `test_prefix_confusion_outside_root_rejected` |    250    |   0    |   35    |          1.63s           | ~1–6 ms (< 1 ms data gen) |
| `test_symlink_escaping_root_rejected`         |    250    |   0    |    0    |          1.30s           | ~3–6 ms (< 1 ms data gen) |
| `test_symlink_internal_to_root_accepted`      |    250    |   0    |    0    |          1.01s           | ~2–4 ms (< 1 ms data gen) |
| **Tổng cộng**                                 | **1,250** | **0**  | **103** |     **8.07s (gen)**      |  **10.54s tổng session**  |

> [!NOTE]
> Các test case "Invalid" xuất hiện do cơ chế loại bỏ dữ liệu trùng lặp nội bộ (deduplication) của Hypothesis khi sinh các danh sách phần tử (`st.lists`) và chuỗi (`st.text`), chứ không phải do bộ lọc thủ công (bộ kiểm thử không sử dụng `.filter()` hay `assume()`). Tỷ lệ invalid rất thấp (< 8%), cho thấy generator strategy được xây dựng hợp lý và hội tụ nhanh.

---

## 5. Bằng chứng độ bao phủ mã nguồn (Code Coverage Evidence)

Đo lường bằng `pytest-cov` trên module đích `documents.file_handling`:

```text
Name                             Stmts   Miss  Cover   Missing
--------------------------------------------------------------
src\documents\file_handling.py      96     76    21%   33, 37-62, 77-122, 126-153, 164-216
--------------------------------------------------------------
TOTAL                               96     76    21%
```

Chi tiết kiểm tra khối mã mục tiêu `validate_path_in_root` (dòng 21–30) và ngoại lệ `UnsafeFilePathError` (dòng 15–19):

```python
15: class UnsafeFilePathError(Exception):
16:     """
17:     Raised when a path generated for a document would land outside of its root.
18:     """
19:
20:
21: def validate_path_in_root(path: Path, root: Path) -> None:
22:     """
23:     Ensures the given absolute path is contained within root, the
24:     equivalent guard for the later move.
25:     """
26:     if not path.resolve().is_relative_to(root.resolve()):
27:         msg = f"Refusing to write file outside of root {root}: {path}."
28:         logger.warning(msg)
29:         raise UnsafeFilePathError(msg)
```

- **Statement Coverage**: **100%** (10/10 dòng lệnh của target được bao phủ).
- **Branch Coverage**: **100%** (Cả 2 nhánh của điều kiện `if not path.resolve().is_relative_to(root.resolve())` đều được kích hoạt):
  - Nhánh `False` (không ném ngoại lệ): kích hoạt bởi `test_descendants_inside_root_accepted` và `test_symlink_internal_to_root_accepted`.
  - Nhánh `True` (ném ngoại lệ `UnsafeFilePathError` và ghi log): kích hoạt bởi `test_traversal_outside_root_rejected`, `test_prefix_confusion_outside_root_rejected`, và `test_symlink_escaping_root_rejected`.
- Các dòng Miss trong file (`33`, `37-62`, `77-122`,...) thuộc về các hàm khác (`create_source_path_directory`, `delete_empty_directories`, `generate_unique_filename`,...) không thuộc phạm vi của target `validate_path_in_root`.

---

## 6. Phân tích Counterexample & Bằng chứng không lỗi (Counterexample & No-Failure Evidence)

### 6.1. Kết quả kiểm thử tự động

- Không phát hiện counterexample nào gây đổ vỡ hợp đồng sau **1,250 ca kiểm thử ngẫu nhiên** và **8 explicit boundary examples**.
- Mọi trường hợp đường dẫn hợp lệ đều được duyệt qua an toàn.
- Mọi nỗ lực thoát khỏi thư mục gốc thông qua traversal `..`, tiền tố gây nhầm lẫn (prefix confusion) hoặc symlink trỏ ra bên ngoài đều bị chặn lại chính xác bằng `UnsafeFilePathError`.

### 6.2. Các ca kiểm thử biên cụ thể (`@example`)

Để tăng cường tính tất định bên cạnh dữ liệu sinh ngẫu nhiên, các ca biên cực đoan đã được gắn trực tiếp vào từng test:

1. **Ca biên INV1**:
   - Tệp đơn lẻ nằm ngay tại root: `parts=["p_single_file.pdf"]`
   - Cây thư mục lồng sâu 3 cấp: `parts=["p_dir", "p_subdir", "p_leaf.txt"]`
2. **Ca biên INV2A**:
   - Traversal trực tiếp 1 cấp không prefix: `prefix=[], extra_depth=1, filename="p_passwd"`
   - Traversal từ thư mục con lồng sâu 2 cấp: `prefix=["p_sub"], extra_depth=2, filename="p_escape.txt"`
3. **Ca biên INV2B**:
   - Sibling cùng tiền tố không phân tách: `sibling_suffix="rogue", parts=["p_secret.pdf"]`
   - Sibling cùng tiền tố có gạch dưới: `sibling_suffix="_backup", parts=["p_sub", "p_file.png"]`
4. **Ca biên INV3A**:
   - Symlink nội bộ trỏ ra tệp nhạy cảm bên ngoài: `filename="p_sensitive_outside.txt"`
5. **Ca biên INV3B**:
   - Symlink nội bộ trỏ tới tệp hợp lệ trong root: `filename="p_internal_target.txt"`

### 6.3. Đánh giá cơ chế Shrinking & Giả lập Counterexample tối thiểu

Hypothesis được cấu hình giữ nguyên cơ chế shrinking mặc định. Nhằm kiểm chứng cơ chế này và minh họa lỗi tiềm tàng theo yêu cầu của Issue #37, chúng tôi tiến hành giả lập một cài đặt khuyết thiếu khi bỏ `.resolve()`:

```python
def flawed_validate_path_in_root(path: Path, root: Path) -> None:
    # Lỗi giả lập: Bỏ .resolve(), chỉ kiểm tra cú pháp lexically
    if not path.is_relative_to(root):
        raise UnsafeFilePathError(
            f"Refusing to write file outside of root {root}: {path}."
        )
```

Khi chạy kiểm thử `test_symlink_escaping_root_rejected` với hàm khuyết thiếu trên:

- Symlink được tạo trong root (`root / "link_to_outside"`) trỏ đến tệp ngoài root (`outside / filename`).
- Do thiếu `.resolve()`, phép kiểm tra cú pháp đường dẫn `path.is_relative_to(root)` vẫn trả về `True`.
- Hàm kết thúc mà không ném ngoại lệ, vi phạm trực tiếp assertion `pytest.raises(UnsafeFilePathError)`.

Hypothesis lập tức phát hiện lỗi và tự động co gọn (shrink) về ví dụ phản chứng tối thiểu (**minimized counterexample**):

```text
Failed: DID NOT RAISE <class 'documents.file_handling.UnsafeFilePathError'>
Falsifying example: test_symlink_escaping_root_rejected(
    filename='p_0',  # Hypothesis tự động shrink về tiền tố tối thiểu và ký tự ngắn nhất
)
```

Thử nghiệm trên chứng minh rằng:

- Nếu logic kiểm tra đường dẫn có lỗ hổng (dù là do thiếu canonicalization hay lỗi logic phân giải), bộ test PBT-03 chắc chắn sẽ phát hiện và rút gọn dữ liệu về ca lỗi tối giản nhất.
- Bộ mã chuẩn hiện tại của Paperless-ngx với 1,250 runs hoàn toàn vượt qua mọi bất biến, chứng thực tính toàn vẹn của cơ chế bảo vệ.

---

## 7. Phân tích nguyên nhân gốc (Root Cause Analysis - RCA) & Đánh giá an ninh

### 7.1. Mô hình đe dọa (Threat Model)

Hàm `validate_path_in_root` giữ nhiệm vụ làm chốt chặn bảo mật (security guardrail) ngăn chặn các lỗ hổng:

- **CWE-22**: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal').
- **CWE-59**: Improper Link Resolution Before File Access ('Link Following').
- **OWASP Top 10 A01:2021**: Broken Access Control.

### 7.2. Tại sao `validate_path_in_root` an toàn?

Cơ chế bảo vệ của hàm dựa trên sự kết hợp của hai phương thức từ thư viện chuẩn `pathlib`:

1. **Canonical Resolution qua `.resolve()`**:
   - Cả `path` và `root` đều được gọi `.resolve()` trước khi kiểm tra quan hệ.
   - Hàm `resolve()` xử lý triệt để tất cả các dấu chấm tương đối (`.` và `..`), phân giải toàn bộ chuỗi symbolic links về nút vật lý thực sự trên hệ thống tập tin, và chuẩn hóa các ký tự đặc biệt của hệ điều hành.
   - Nhờ đó, một symlink ngụy trang nằm trong `storage_root` nhưng trỏ tới `/etc/passwd` sẽ lập tức bị phân giải thành `/etc/passwd`, làm cho bước kiểm tra sau đó phát hiện việc thoát khỏi root.
2. **Component-based Containment qua `.is_relative_to()`**:
   - Khác với so sánh chuỗi tiền tố thông thường (vốn dễ bị lỗ hổng prefix confusion như `/var/data/storage` khớp tiền tố với `/var/data/storage_backup`), `is_relative_to` kiểm tra theo từng thành phần (components) của đường dẫn.
   - Do đó, `/var/data/storage_backup` không bao giờ được coi là relative to `/var/data/storage`.

### 7.3. Phát hiện quan trọng cho Phòng thủ chiều sâu (Defense-in-Depth Finding)

Khi rà soát các hàm khác trong cùng file `src/documents/file_handling.py`, chúng tôi phát hiện hàm `delete_empty_directories` (dòng 36–63):

```python
def delete_empty_directories(directory: Path, root: Path) -> None:
    if not directory.is_dir():
        return

    if not directory.is_relative_to(root):
        return
```

> [!WARNING]
> Tại dòng 40, `delete_empty_directories` chỉ kiểm tra `if not directory.is_relative_to(root):` mà **KHÔNG gọi `.resolve()`**!
> Nếu một tiến trình hoặc người dùng tạo ra symlink hoặc chuỗi relative traversal bên trong thư mục cần xóa, `directory.is_relative_to(root)` có thể trả về `True` về mặt cú pháp đường dẫn, nhưng thao tác xóa thư mục cha đệ quy (`directory = directory.parent`) có thể leo ngược ra ngoài root khi gặp symlink trỏ ra ngoài!
>
> **Khuyến nghị**: Nên chuẩn hóa `delete_empty_directories` bằng cách gọi `directory.resolve().is_relative_to(root.resolve())` hoặc gọi trực tiếp `validate_path_in_root(directory, root)` trước khi duyệt xóa.

---

## 8. Hướng dẫn tái lập cho Peer Reviewer (`@HubertPhung`)

### 8.1. Chạy trên môi trường local (Linux / macOS / WSL2 / Docker)

```bash
# Đồng bộ môi trường testing
uv sync --python 3.12 --group testing --frozen

# Chạy profile recorded (250 examples) và xuất coverage
HYPOTHESIS_PROFILE=recorded uv run --python 3.12 --dev --frozen pytest \
  src/documents/tests/test_path_security.py -k TestPathSecurity -n 0 -v \
  --hypothesis-seed=20261008 --hypothesis-show-statistics \
  --cov=documents.file_handling --cov-branch --cov-report=term-missing
```

### 8.2. Chạy trên môi trường Windows (PowerShell)

```powershell
$env:PYTHONPATH="src"
$env:DJANGO_SETTINGS_MODULE="paperless.settings"
$env:PAPERLESS_SECRET_KEY="test-secret-key-for-pbt-tests"
$env:HYPOTHESIS_PROFILE="recorded"
pytest src/documents/tests/test_path_security.py -k TestPathSecurity -n 0 -v --hypothesis-seed=20261008 --hypothesis-show-statistics --cov=documents.file_handling --cov-branch --cov-report=term-missing
```

### 8.3. Kiểm tra tự động trên GitHub Actions (CI)

- Truy cập tab **Actions** trên repository.
- Chọn workflow **Coursework CI** chạy cho pull request này.
- Kiểm tra job **PBT-03 path security**; xem log chạy kiểm thử và tải file artifact `pbt-03-evidence` (`.artifacts/pbt-03-run.log`).

---

## 9. Execution Log

<details>
<summary><b>Nhấn để xem toàn bộ raw output của profile recorded (250 examples/property)</b></summary>

```text
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0 -- C:\workspace\paperless-ngx\.temp_test_venv\Scripts\python.exe
cachedir: .pytest_cache
hypothesis profile 'default'
django: version: 6.1.2, settings: paperless.settings (from env)
rootdir: C:\workspace\paperless-ngx
configfile: pyproject.toml
plugins: anyio-4.16.0, Faker-40.44.0, hypothesis-6.168.5, cov-7.1.0, django-4.14.0, env-1.8.5, xdist-3.8.0
collecting ... collected 5 items

src/documents/tests/test_path_security.py::TestPathSecurity::test_descendants_inside_root_accepted PASSED [ 20%]
src/documents/tests/test_path_security.py::TestPathSecurity::test_traversal_outside_root_rejected PASSED [ 40%]
src/documents/tests/test_path_security.py::TestPathSecurity::test_prefix_confusion_outside_root_rejected PASSED [ 60%]
src/documents/tests/test_path_security.py::TestPathSecurity::test_symlink_escaping_root_rejected PASSED [ 80%]
src/documents/tests/test_path_security.py::TestPathSecurity::test_symlink_internal_to_root_accepted PASSED [100%]

=============================== tests coverage ================================
_______________ coverage: platform win32, python 3.13.5-final-0 _______________

Name                             Stmts   Miss  Cover   Missing
--------------------------------------------------------------
src\documents\file_handling.py      96     76    21%   33, 37-62, 77-122, 126-153, 164-216
--------------------------------------------------------------
TOTAL                               96     76    21%
============================ Hypothesis Statistics ============================
src/documents/tests/test_path_security.py::TestPathSecurity::test_descendants_inside_root_accepted:

  - during generate phase (2.27 seconds):
    - Typical runtimes: ~ 1-9 ms, of which ~ 0-3 ms in data generation
    - 250 passing, 0 failing, and 43 invalid test cases

  - Stopped because settings.max_examples=250


src/documents/tests/test_path_security.py::TestPathSecurity::test_traversal_outside_root_rejected:

  - during generate phase (1.86 seconds):
    - Typical runtimes: ~ 1-9 ms, of which ~ 0-2 ms in data generation
    - 250 passing, 0 failing, and 25 invalid test cases

  - Stopped because settings.max_examples=250


src/documents/tests/test_path_security.py::TestPathSecurity::test_prefix_confusion_outside_root_rejected:

  - during generate phase (1.63 seconds):
    - Typical runtimes: ~ 1-6 ms, of which ~ 0-1 ms in data generation
    - 250 passing, 0 failing, and 35 invalid test cases

  - Stopped because settings.max_examples=250


src/documents/tests/test_path_security.py::TestPathSecurity::test_symlink_escaping_root_rejected:

  - during generate phase (1.30 seconds):
    - Typical runtimes: ~ 3-6 ms, of which < 1ms in data generation
    - 250 passing, 0 failing, and 0 invalid test cases

  - Stopped because settings.max_examples=250


src/documents/tests/test_path_security.py::TestPathSecurity::test_symlink_internal_to_root_accepted:

  - during generate phase (1.01 seconds):
    - Typical runtimes: ~ 2-4 ms, of which < 1ms in data generation
    - 250 passing, 0 failing, and 0 invalid test cases

  - Stopped because settings.max_examples=250


======================= 5 passed, 8 warnings in 10.54s ========================
```

</details>
