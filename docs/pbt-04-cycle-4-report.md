# PBT-04 Cycle 4: Báo cáo tổng kết, Hướng dẫn tái lập máy sạch & Kịch bản Demo bảo vệ

## Thông tin chung & Phân công

- **Issue**: [#51 — [Cycle 4][Huỳnh] Final report & demo PBT-04 MIME-extension](https://github.com/0Yaam/paperless-ngx/issues/51)
- **Người thực hiện (Owner)**: Vũ Thế Huỳnh (`@1convitt`)
- **Người review chéo (Peer Reviewer)**: Phan Khánh Vương (`@vuong123s`)
- **Suite**: `PBT-04` — Kiểm chứng ánh xạ MIME và phần mở rộng tệp (`MIME-extension helpers`)
- **Hàm mục tiêu (Target)**: 4 hàm helper trong [`src/documents/parsers.py`](../src/documents/parsers.py#L25-L68):
  - `is_mime_type_supported(mime_type: str) -> bool` (`L25–29`)
  - `get_default_file_extension(mime_type: str) -> str` (`L32–44`)
  - `is_file_ext_supported(ext: str) -> bool` (`L47–55`)
  - `get_supported_file_extensions() -> set[str]` (`L58–68`)
- **Baseline nhánh fork cố định**: `dev@b29fec117053637428a935d43af16d9e1d65c1fb` (tương thích nguyên vẹn mã nguồn và test trên `dev@0944d0352` và `dev@afbd50b68`)
- **Baseline upstream**: `da3de299f`
- **Tài liệu các Cycle trước**:
  - Thiết kế Cycle 1: [`pbt-04-mime-extension-design.md`](pbt-04-mime-extension-design.md) (Issue [#13](https://github.com/0Yaam/paperless-ngx/issues/13))
  - PR triển khai Cycle 2: [#31](https://github.com/0Yaam/paperless-ngx/pull/31) (`dfd1e882a`)
  - Bằng chứng & RCA Cycle 3: [`pbt-04-cycle-3-evidence.md`](pbt-04-cycle-3-evidence.md) (PR [#46](https://github.com/0Yaam/paperless-ngx/pull/46) `12734fddc`, Issue [#38](https://github.com/0Yaam/paperless-ngx/issues/38))

---

## 1. Báo cáo tổng kết PBT-04 (Chuẩn cấu trúc Phần A–H)

### Phần A — Mục tiêu hệ thống & Ngữ cảnh luồng dữ liệu

Trong Paperless-ngx, mọi tài liệu đi qua đường ống tiếp nhận (`documents.consumer`, thư mục `consume/`, REST API `POST /api/documents/post_document/` và quy tắc email) đều phải được kiểm tra định dạng trước khi phân loại, lưu trữ file gốc/lưu trữ hoặc dựng tên tệp tải về. Lớp [`documents.parsers`](../src/documents/parsers.py#L25-L68) cung cấp 4 hàm cầu nối dùng chung với [`ParserRegistry`](../src/paperless/parsers/registry.py#L151):

- `is_mime_type_supported(mime_type)`: xác định có parser khả dụng nào xử lý được `mime_type` ở cấu hình hiện tại hay không.
- `get_default_file_extension(mime_type)`: suy luận phần mở rộng mặc định cho một MIME (phục vụ lưu trữ, xuất tệp và đặt tên an toàn).
- `is_file_ext_supported(ext)`: kiểm tra nhanh phần mở rộng tệp có nằm trong tập phần mở rộng hỗ trợ hay không.
- `get_supported_file_extensions()`: tổng hợp toàn bộ phần mở rộng và alias hợp lệ từ mọi parser đã đăng ký.

Phạm vi của `PBT-04` giới hạn ở hợp đồng ánh xạ MIME–extension của 4 helper trên; cơ chế chấm điểm ưu tiên, tie-break external/built-in và lọc `allow_remote` thuộc `PBT-05`, còn quá trình chuyển đổi ảnh/thumbnail (`run_convert`, `make_thumbnail_from_pdf`, `DocumentParser`) nằm ngoài phạm vi suite.

### Phần B — Kiến trúc, Cơ chế hoạt động & 4 Trọng tâm của Suite

Bốn trọng tâm chuyên môn của `PBT-04` được thiết kế dựa trên hành vi thực tế trong [`src/documents/parsers.py`](../src/documents/parsers.py#L25-L68):

1. **Platform MIME aliases (`mimetypes.guess_all_extensions`)**:
   - Hàm `get_supported_file_extensions()` (`L58–68`) duyệt tất cả lớp parser trong `get_parser_registry().all_parsers()` và mọi cặp `(mime_type, ext)` từ `parser_class.supported_mime_types().items()`.
   - Với mỗi `mime_type`, hàm gộp cả **alias từ thư viện chuẩn của hệ điều hành** (`mimetypes.guess_all_extensions(mime_type)`, ví dụ `.jpeg`, `.jpe`, `.jpg` cho `image/jpeg`) và **chủ động thêm default extension của parser** (`extensions.add(ext)` ở `L66`). Việc cộng thêm `ext` bảo đảm các định dạng mới như `image/webp` (`.webp`) hoặc `image/heic` (`.heic`) không bị rơi mất nếu bảng `mimetypes` của OS hoặc Python cũ hơn chưa cập nhật.
   - Vì bảng alias của `mimetypes` phụ thuộc nền tảng (Linux vs Windows), các bài test trên built-in registry lấy snapshot ngay trong cùng môi trường chạy, còn `PBT04-INV3` dùng bảng alias giả xác định để kiểm chứng phép hợp tập hợp độc lập với host.

2. **Kiểm tra thành viên không phân biệt hoa/thường (`Case-insensitive membership`)**:
   - Hàm `is_file_ext_supported(ext)` (`L47–55`) kiểm tra điều kiện `if ext:`; nếu khác rỗng thì chuẩn hóa `ext.lower()` trước khi tra cứu trong `get_supported_file_extensions()`, ngược lại trả `False` cho chuỗi rỗng `""`.
   - Hàm cố ý không tự thêm dấu chấm (nên `"pdf"` trả `False`), không cắt khoảng trắng hai đầu, và không đặt quy tắc case-insensitive cho `mime_type`.

3. **Nhất quán giữa Registry và Default Extension (`Registry/default consistency`)**:
   - `is_mime_type_supported(mime_type)` (`L29`) và `get_default_file_extension(mime_type)` (`L37`) đều truy vấn `get_parser_registry().get_parser_for_file(mime_type, "")` — tức phụ thuộc trạng thái `score()` của từng parser tại thời điểm chạy (ví dụ `TikaDocumentParser.score()` trả `None` khi `TIKA_ENABLED=False`, khiến các MIME Office không được xem là supported ở cấu hình tắt Tika).
   - Ngược lại, `get_supported_file_extensions()` đọc `all_parsers()` và không lọc theo `score()`, nên các extension như `.docx` vẫn xuất hiện trong `get_supported_file_extensions()` ngay cả khi `TIKA_ENABLED=False`.
   - Với mọi MIME được `is_mime_type_supported(mime)` trả `True`, default extension trả về phải là chuỗi bắt đầu bằng `.`, dài tối thiểu `2`, không chứa khoảng trắng/`/`/`\`, và luôn nằm trong `get_supported_file_extensions()`.

4. **Nhánh Fallback (`The fallback branch`)**:
   - Trong `get_default_file_extension(mime_type)` (`L37–44`) có hai đường rơi xuống `mimetypes.guess_extension(mime_type)`:
     - **Đường 1 (`parser_class is None`, `L38 False -> L43`)**: Không có parser nào nhận `mime_type` (ví dụ `application/zip`), hàm vẫn fallback sang `mimetypes.guess_extension` và trả `".zip"` (hoặc `""` nếu không đoán được, như `application/x-pbt-unknown`). Điều này chứng minh **có extension fallback không đồng nghĩa `is_mime_type_supported(mime)` là `True`**.
     - **Đường 2 (`parser_class is not None` nhưng `mime_type not in supported`, `L40 False -> L43`)**: Nhánh phòng thủ khi một parser được chọn nhưng từ điển `supported_mime_types()` của nó không chứa khóa `mime_type`, hàm cũng fallback sang `mimetypes.guess_extension`. Nhánh này được khóa kín ở Cycle 3 bằng `test_parser_without_mapping_uses_mimetypes_fallback`.

### Phần C — Môi trường & Baseline đã kiểm chứng

- **Baseline nhánh fork cố định**: `dev@b29fec117053637428a935d43af16d9e1d65c1fb` (mã nguồn mục tiêu và bộ kiểm thử giữ nguyên trên `dev@0944d0352` và `dev@afbd50b68`).
- **Phiên bản môi trường chuẩn hóa (`uv.lock`)**: Ubuntu Runner (`ubuntu-latest`), Python `3.12`, khóa phụ thuộc `uv sync --python 3.12 --group testing --frozen`.
- **Cấu hình chạy tất định**:
  - `HYPOTHESIS_PROFILE=recorded` (`max_examples=250`, `deadline=None`, `print_blob=True`).
  - Hạt giống cố định: `--hypothesis-seed=13`, chạy đơn tiến trình `-n 0`, đo nhánh `--cov=documents.parsers --cov-branch --cov-report=term-missing`.
- **Các lần chạy GitHub Actions CI xác thực (job `PBT-04 MIME-extension`, artifact `pbt-04-evidence`)**:
  - Trên baseline `b29fec117`: [Coursework CI Run #45764068014](https://github.com/0Yaam/paperless-ngx/actions/runs/45764068014) (`2026-11-26T05:49:22Z -> 05:50:47Z`) — **success**, artifact `pbt-04-evidence` (`15,059` bytes).
  - Trên `dev@0944d0352`: [Coursework CI Run #45791632304](https://github.com/0Yaam/paperless-ngx/actions/runs/45791632304) (`2026-11-26T09:24:15Z -> 09:25:23Z`) — **success**, artifact `pbt-04-evidence` (`15,026` bytes).
  - Trên `dev@afbd50b68`: [Coursework CI Run #46032835163](https://github.com/0Yaam/paperless-ngx/actions/runs/46032835163) (`2026-11-27T16:20:57Z -> 16:22:18Z`) — **success**, artifact `pbt-04-evidence` (`15,054` bytes).
- **Đối chứng Cycle 3 cục bộ** (ghi trong [`pbt-04-cycle-3-evidence.md`](pbt-04-cycle-3-evidence.md)): Python `3.12.15`, `pytest 9.2.0`, `Hypothesis 6.170.17`, `coverage.py 7.17.5` trên Windows.

### Phần D — Cơ sở kỹ thuật K01 PBT, Phạm vi, Giả định & Tiêu chí Pass/Fail

- **Vì sao áp dụng Property-Based Testing (K01)**: Tập phần mở rộng hỗ trợ phụ thuộc vào tích hợp nhiều parser mapping chồng chéo, alias từ hệ điều hành, và tập biến thể chữ hoa/thường theo từng ký tự ($2^L$ tổ hợp cho chuỗi dài $L$ tới 32 ký tự). Kiểm thử bảng ví dụ tĩnh dễ bỏ sót chuỗi rỗng, dấu tách đường dẫn bất thường, biến thể hoa/thường hỗn hợp hoặc thiếu phần tử khi hợp nhiều parser.
- **Giả định & Giới hạn cô lập**:
  - Hai nhóm property trên built-in registry dùng `_isolated_builtin_registry(tika_enabled=...)` (`override_settings`, `ParserRegistry().register_defaults()`, patch `get_parser_registry` và patch `RemoteDocumentParser.score` về `None`) để không kích hoạt plugin bên ngoài hay truy vấn cấu hình DB/OCR từ xa.
  - `test_registry_extensions_include_defaults_and_aliases` mock `get_parser_registry` (tối đa 5 parser, mỗi parser tối đa 8 mapping) và `mimetypes.guess_all_extensions` (tối đa 4 alias/MIME) để cô lập hoàn toàn logic hợp tập hợp khỏi bảng MIME của OS.
- **Tiêu chí Pass/Fail (Acceptance Gate)**:
  - `13/13` test cases trong `TestMimeExtensionProperties` đạt `PASSED` (`14` test ở `TestParserAvailability` bị deselected đúng bộ lọc `-k TestMimeExtensionProperties`).
  - Không có ca `failing` ở bất kỳ property nào; hai property miền không giới hạn đạt `250 passing` và hai biến thể hữu hạn cùng `test_all_builtin_mappings[False/True]` quét trọn toàn bộ MIME built-in.
  - 4 hàm mục tiêu đạt **100% statement (`21/21`)** và **100% branch (`10/10`)** với `0` dòng/nhánh thiếu.

### Phần E — Mô hình Property, Bất biến & Ca kiểm thử xác định

Lớp [`TestMimeExtensionProperties`](../src/documents/tests/test_parsers.py#L202-L339) triển khai **3 họ property Hypothesis** (chạy thành 4 lượt kiểm thử theo biến cấu hình `tika_enabled`), kèm **9 ca kiểm thử xác định** cho quét vét cạn, hồi quy case và nhánh fallback:

| Mã Invariant | Hàm kiểm thử                                            | Chiến lược sinh & Biến cấu hình                                                                                  | Oracle kiểm chứng                                                                                                                         |
| :----------- | :------------------------------------------------------ | :--------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------- |
| `PBT04-INV1` | `test_supported_mime_has_valid_extension[False\|True]`  | `st.sampled_from(mimes)` từ built-in registry (`TIKA_ENABLED=False` và `True`)                                   | `get_default_file_extension(mime)` bắt đầu bằng `.`, dài $\ge 2$, không chứa space/`/`/`\`, thuộc `get_supported_file_extensions()`       |
| `PBT04-INV2` | `test_extension_membership_is_case_insensitive`         | Hợp của `sampled_from(extensions)` và ASCII dài `0..32` (`._- ` + chữ/số), kèm mảng boolean đảo hoa/thường       | `is_file_ext_supported(ext)` và `is_file_ext_supported(variant)` đều bằng `bool(ext) and ext.lower() in extensions`                       |
| `PBT04-INV3` | `test_registry_extensions_include_defaults_and_aliases` | `0..5` parser giả, `0..8` MIME `application/x-pbt-<token>`, `0..4` alias/MIME + 2 `@example` (rỗng & trùng)      | `get_supported_file_extensions()` bằng chính xác hợp của mọi default và mọi alias trong dữ liệu sinh                                      |
| `PBT04-DET1` | `test_all_builtin_mappings[False\|True]`                | Quét vét cạn toàn bộ MIME built-in ở `TIKA_ENABLED=False` và `True`                                              | Mọi MIME được hỗ trợ thỏa `_assert_valid_default_extension`; `.docx` luôn có trong extensions nhưng chỉ supported khi `TIKA_ENABLED=True` |
| `PBT04-DET2` | `test_extension_regressions`                            | 5 ca biên: `(".PDF", True)`, `(".JpEg", True)`, `("", False)`, `("pdf", False)`, `(".not-supported-pbt", False)` | Khớp chính xác giá trị kỳ vọng cho hoa/thường, chuỗi rỗng, thiếu dấu chấm và chuỗi ngoài tập                                              |
| `PBT04-DET3` | `test_fallback_does_not_imply_mime_support`             | `application/zip` (có alias `.zip`) và `application/x-pbt-unknown` (không có trong `mimetypes`)                  | `is_mime_type_supported` trả `False` cho cả hai; fallback trả `".zip"` và `""` tương ứng                                                  |
| `PBT04-DET4` | `test_parser_without_mapping_uses_mimetypes_fallback`   | Parser giả trả `supported_mime_types() == {}` với `mimetypes.guess_extension` trả `".fallback"`                  | Phủ nhánh phòng thủ `L40 False -> L43`: `get_default_file_extension` trả `".fallback"`                                                    |

### Phần F — Số liệu Cycle 3 & Bằng chứng bao phủ nhánh tất định

1. **Thống kê kết quả chạy từ [`pbt-04-cycle-3-evidence.md`](pbt-04-cycle-3-evidence.md)** (`HYPOTHESIS_PROFILE=recorded`, `--hypothesis-seed=13`, `-n 0`):

   | Property                                                | Passing | Failing | Invalid | Generate time |
   | :------------------------------------------------------ | ------: | ------: | ------: | ------------: |
   | `test_supported_mime_has_valid_extension[False]`        |       7 |       0 |       0 |        0.06 s |
   | `test_supported_mime_has_valid_extension[True]`         |      11 |       0 |       0 |        0.01 s |
   | `test_extension_membership_is_case_insensitive`         |     250 |       0 |      11 |        0.38 s |
   | `test_registry_extensions_include_defaults_and_aliases` |     250 |       0 |      29 |        1.45 s |
   - **Tổng kết phiên chạy**: `13 passed, 14 deselected in 2.13s`, `0` lỗi sản phẩm.
   - **Lý giải số ví dụ hữu hạn**: Hai lượt `test_supported_mime_has_valid_extension[False]` và `[True]` dừng sau `7` và `11` ví dụ vì chiến lược `st.sampled_from(mimes)` chỉ chọn từ tập hữu hạn các MIME built-in nên Hypothesis dừng sớm khi rút cạn không gian mẫu; toàn bộ 12 MIME (tắt Tika) và 24 MIME (bật Tika) vẫn được kiểm tra đầy đủ 100% qua `test_all_builtin_mappings[False|True]`.
   - Số ca `invalid` (`11` và `29`) là các ca trùng lặp do Hypothesis tự khử trùng lặp trong chiến lược sinh ngẫu nhiên, không phải lỗi test.

2. **Độ bao phủ câu lệnh và nhánh mục tiêu (`--cov=documents.parsers --cov-branch`)**:

   | Hàm mục tiêu (`src/documents/parsers.py`)  | Số dòng chạy | Dòng thiếu | Số nhánh chạy | Nhánh thiếu |
   | :----------------------------------------- | -----------: | ---------: | ------------: | ----------: |
   | `is_mime_type_supported` (`L25–29`)        |            2 |          0 |             0 |           0 |
   | `get_default_file_extension` (`L32–44`)    |            8 |          0 |             4 |           0 |
   | `is_file_ext_supported` (`L47–55`)         |            4 |          0 |             2 |           0 |
   | `get_supported_file_extensions` (`L58–68`) |            7 |          0 |             4 |           0 |
   | **Tổng cộng phạm vi mục tiêu (`PBT-04`)**  |       **21** |      **0** |        **10** |       **0** |
   - **Phân tách với tỷ lệ toàn module**: Toàn tệp `src/documents/parsers.py` trong Cycle 3 đạt `45%` vì chứa các hàm chuyển đổi ảnh và lớp nền ngoài phạm vi (`run_convert`, `get_default_thumbnail`, `make_thumbnail_from_pdf_gs_fallback`, `make_thumbnail_from_pdf`, `DocumentParser`). Trong phạm vi mục tiêu của `PBT-04`, cả 4 helper đạt **100% statement (`21/21`)** và **100% branch (`10/10`)**.

### Phần G — Phân tích không lỗi (No-Failure RCA), Kiểm chứng Mutation & Giới hạn

1. **RCA không phát hiện lỗi (`No Production Defect`)**: Toàn bộ 4 hợp đồng đều giữ vững vì:
   - `is_mime_type_supported` ủy quyền trực tiếp cho `get_parser_for_file(mime_type, "")` nên trạng thái hỗ trợ luôn đồng bộ với `score()` của registry.
   - `is_file_ext_supported` chuẩn hóa bằng `ext.lower()` sau khi kiểm tra chuỗi khác rỗng.
   - `get_supported_file_extensions` hợp đồng thời alias `mimetypes` lẫn extension mặc định của từng parser.
   - `get_default_file_extension` chỉ fallback sang `mimetypes.guess_extension` mà không làm sai lệch kết quả của `is_mime_type_supported`.
2. **Kiểm chứng năng lực phát hiện lỗi (Mutation Check từ Cycle 3)**:
   - Bỏ `.lower()` khỏi `is_file_ext_supported`: ca hồi quy `.PDF` lập tức thất bại.
   - Bỏ `extensions.add(ext)` khỏi `get_supported_file_extensions`: `test_registry_extensions_include_defaults_and_aliases` lập tức phát hiện và Hypothesis shrink về phản ví dụ tối thiểu `{"application/x-pbt-a": ".a"}` thiếu `.a`.
3. **Giới hạn ngoài phạm vi**:
   - Bảng alias `mimetypes` khác nhau giữa các hệ điều hành, nên artifact trên Ubuntu CI (`uv.lock`) là chuẩn đối chiếu chính thức.
   - Suite không kiểm tra chạy OCR/ImageMagick/Ghostscript thực tế (`run_convert`, `make_thumbnail_*`) hay nạp plugin bên ngoài qua entry point.
   - Artifact trên GitHub Actions có thời hạn lưu giữ; tài liệu Cycle 3 và báo cáo Cycle 4 lưu giữ lâu dài các số liệu và đường dẫn truy vết.

### Phần H — Lưu cứng phiên bản & Danh mục truy vết

| Thành phần / Mốc đối chiếu          | Mã định danh / Đường dẫn                                                                                                                                                                                                                                      | Ý nghĩa đối chiếu                                                                 |
| :---------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :-------------------------------------------------------------------------------- |
| Baseline nhánh fork cố định         | `dev@b29fec117053637428a935d43af16d9e1d65c1fb`                                                                                                                                                                                                                | Mốc checkout sạch sau khi khép lại toàn bộ Cycle 3 của 5 suite                    |
| Merge commit Cycle 3 PBT-04         | `12734fddcddf47fb5019bb7de74decda07ee93a1` ([PR #46](https://github.com/0Yaam/paperless-ngx/pull/46))                                                                                                                                                         | Khóa profile `recorded`, `-n 0`, `--cov-branch`, test fallback và RCA             |
| Mã nguồn mục tiêu & bộ kiểm thử     | [`parsers.py`](../src/documents/parsers.py#L25-L68), [`test_parsers.py`](../src/documents/tests/test_parsers.py#L202-L339)                                                                                                                                    | 4 helper mục tiêu và lớp `TestMimeExtensionProperties`                            |
| Script tái lập & kiểm chứng tự động | [`scripts/demo-pbt-04.sh`](../scripts/demo-pbt-04.sh)                                                                                                                                                                                                         | Kiểm tra baseline, không drift mã nguồn, chạy pytest, xác minh coverage JSON      |
| Workflow CI & Artifact              | [`coursework-ci.yml`](../.github/workflows/coursework-ci.yml#L16), `pbt-04-evidence`                                                                                                                                                                          | Chạy `demo-pbt-04.sh` + parser regressions trên Ubuntu Python 3.12 và lưu log/XML |
| Các lần chạy CI xác thực trên `dev` | [Run #45764068014](https://github.com/0Yaam/paperless-ngx/actions/runs/45764068014), [Run #45791632304](https://github.com/0Yaam/paperless-ngx/actions/runs/45791632304), [Run #46032835163](https://github.com/0Yaam/paperless-ngx/actions/runs/46032835163) | Bằng chứng job `PBT-04 MIME-extension` xanh trước Cycle 4                         |

---

## 2. Hướng dẫn tái lập trên máy sạch (Clean-Machine Reproduction)

### Điều kiện tiên quyết

- Hệ điều hành: **Linux, macOS hoặc WSL2** (`uv.lock` của repository giới hạn các marker wheel cho `linux` và `darwin`; Windows thuần không phải môi trường đồng bộ `uv.lock` được hỗ trợ).
- Công cụ: `git`, Astral `uv` (`0.12.x`), kết nối mạng cho lần đồng bộ gói đầu tiên.

### Chạy trực tiếp từ bản checkout sạch của baseline cố định

```bash
# 1. Clone mới repository và checkout đúng baseline Cycle 4
git clone --branch dev https://github.com/0Yaam/paperless-ngx.git
cd paperless-ngx
git checkout b29fec117053637428a935d43af16d9e1d65c1fb

# 2. Cài đặt chính xác các phụ thuộc kiểm thử đã khóa trong uv.lock
uv sync --python 3.12 --group testing --frozen

# 3. Chạy PBT-04 tất định với profile recorded, seed=13 và đo branch coverage
HYPOTHESIS_PROFILE=recorded uv run --python 3.12 --group testing --frozen pytest \
  src/documents/tests/test_parsers.py -k TestMimeExtensionProperties -n 0 -v \
  --hypothesis-seed=13 --hypothesis-show-statistics \
  --cov=documents.parsers --cov-branch --cov-report=term-missing
```

_(Tùy chọn chạy toàn bộ hồi quy parser để kiểm tra không rò rỉ trạng thái registry:)_

```bash
uv run --python 3.12 --group testing --frozen pytest \
  src/documents/tests/test_parsers.py -n 0 --hypothesis-seed=13
```

### Chạy bằng script tự động trên nhánh `dev` cuối kỳ

```bash
bash scripts/demo-pbt-04.sh
```

Script tự động thực hiện: (1) xác nhận `HEAD` kế thừa từ `b29fec117053637428a935d43af16d9e1d65c1fb`, (2) kiểm tra không có sai lệch mã nguồn ở `src/documents/parsers.py` và `src/documents/tests/test_parsers.py`, (3) đồng bộ `uv sync --python 3.12 --group testing --frozen`, (4) chạy `TestMimeExtensionProperties` với `HYPOTHESIS_PROFILE=recorded` và `--hypothesis-seed=13`, (5) xác nhận `13 passed, 14 deselected`, thống kê Hypothesis và độ phủ `21/21` dòng, `10/10` nhánh cho 4 helper, đồng thời ghi artifact vào `.artifacts/pbt-04-cycle-4/` (`environment.txt`, `pbt-04-run.log`, `properties.xml`, `coverage.json`, `verification.json`).

### Đầu ra & Thống kê kỳ vọng

- **Pytest summary**: `13 passed, 14 deselected`.
- **Hypothesis Statistics**:
  - `test_supported_mime_has_valid_extension[False|True]`: dừng sớm sau khi rút cạn tập hữu hạn (`7` và `11` ca `passing`, `0` `failing`), bổ trợ bởi `test_all_builtin_mappings[False|True]` (`PASSED`).
  - `test_extension_membership_is_case_insensitive`: `250 passing, 0 failing`.
  - `test_registry_extensions_include_defaults_and_aliases`: `250 passing, 0 failing`.
- **Target Coverage**: `21/21` executable lines và `10/10` branches (`0` missing lines/branches) trên 4 hàm mục tiêu.
- **Vị trí Artifact trên GitHub Actions**: Workflow **Coursework CI** $\rightarrow$ job **PBT-04 MIME-extension** $\rightarrow$ artifact **`pbt-04-evidence`** (chứa `environment.txt`, `pbt-04-run.log`, `properties.xml`, `coverage.json`, `verification.json`, `regressions.log`, `regressions.xml`).

---

## 3. Kịch bản Demo bảo vệ cuối kỳ (3–5 phút)

Thực hiện tuần tự 4 bước sau tại buổi bảo vệ mà không cần thiết lập ngầm ngoài tài liệu:

1. **Xác nhận baseline và tính toàn vẹn mã nguồn (30 giây)**:

   ```bash
   git rev-parse --short HEAD
   git diff --stat b29fec117053637428a935d43af16d9e1d65c1fb HEAD -- src/documents/parsers.py src/documents/tests/test_parsers.py
   ```

   Kỳ vọng: `git diff --stat` không in ra sai khác nào (mã nguồn mục tiêu và bộ kiểm thử khớp nguyên bản baseline).

2. **Chạy trực tiếp script demo và giải thích 4 trọng tâm (2 phút)**:

   ```bash
   bash scripts/demo-pbt-04.sh
   ```

   Chỉ trực tiếp trên output `pytest` và `verification.json`:
   - **Platform MIME aliases & đồng nhất registry/default**: `test_registry_extensions_include_defaults_and_aliases` (`250 passing`) gộp cả default extension của parser và alias từ `mimetypes`; `test_all_builtin_mappings[False|True]` chứng minh `.docx` luôn có trong `get_supported_file_extensions()` nhưng chỉ `is_mime_type_supported` trả `True` khi `TIKA_ENABLED=True`.
   - **Case-insensitive membership**: `test_extension_membership_is_case_insensitive` (`250 passing`) và `test_extension_regressions` (`.PDF`, `.JpEg`, `""`, `"pdf"`).
   - **Hai nhánh fallback**: `test_fallback_does_not_imply_mime_support` (`application/zip` -> `.zip` nhưng `is_mime_type_supported` là `False`) và `test_parser_without_mapping_uses_mimetypes_fallback`.
   - **Target coverage**: chỉ rõ `21/21` dòng và `10/10` nhánh trong `verification.json`.

3. **Minh họa khả năng phát hiện lỗi bằng Mutation Check (60 giây — tùy chọn)**:
   Trình bày hai đột biến đã kiểm chứng trong Cycle 3 (không sửa file Git khi bảo vệ):
   - Bỏ `.lower()` làm ca hồi quy `.PDF` thất bại ngay.
   - Bỏ `extensions.add(ext)` làm `test_registry_extensions_include_defaults_and_aliases` tự shrink về `{"application/x-pbt-a": ".a"}` thiếu `.a`.

4. **Phương án dự phòng khi Demo (Fallback)**:
   - **Tình huống A (Máy bảo vệ chỉ có Windows bản địa, không dùng được `uv.lock`)**: Chạy trong WSL2/Ubuntu hoặc mở trực tiếp kết quả chạy Linux chuẩn hóa của GitHub Actions `Coursework CI`.
   - **Tình huống B (Mất mạng hoặc không đồng bộ được `uv` tại buổi bảo vệ)**: Mở trực tiếp tệp `pbt-04-run.log`, `verification.json`, `regressions.log` đã tải sẵn từ artifact `pbt-04-evidence` của `Coursework CI`.

---

## 4. Bằng chứng Review chéo (Peer-Review Evidence) & Checklist nghiệm thu

### Lịch sử Review chéo qua các Cycle

| Giai đoạn | Pull Request / Issue                                                                                                     | Người review | Nội dung góp ý & Chỉnh sửa                                                                                                                                                                                | Kết quả & Commit                          |
| :-------- | :----------------------------------------------------------------------------------------------------------------------- | :----------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------- |
| Cycle 1–2 | [PR #31](https://github.com/0Yaam/paperless-ngx/pull/31) (Issue [#13](https://github.com/0Yaam/paperless-ngx/issues/13)) | `@vuong123s` | Thiết kế 3 invariant độc lập, bổ sung `TestMimeExtensionProperties` với registry cô lập và job `pbt-04` trong `coursework-ci.yml`; xử lý góp ý format/CI trước khi hợp nhất.                              | Đã merge `dfd1e882a` (`2026-10-13`)       |
| Cycle 3   | [PR #46](https://github.com/0Yaam/paperless-ngx/pull/46) (Issue [#38](https://github.com/0Yaam/paperless-ngx/issues/38)) | Nhóm / CI    | Bổ sung profile `recorded` (`max_examples=250`), chạy nối tiếp `-n 0` với `--hypothesis-seed=13`, `--cov-branch`, tài liệu `pbt-04-cycle-3-evidence.md` và test phủ nhánh phòng thủ `mimetypes` fallback. | Đã merge `12734fddc` (`2026-11-26`)       |
| Cycle 4   | Issue [#51](https://github.com/0Yaam/paperless-ngx/issues/51)                                                            | `@vuong123s` | Hoàn thiện báo cáo A–H, giải thích 4 trọng tâm của suite, viết `scripts/demo-pbt-04.sh`, gắn vào `Coursework CI` và lập kịch bản demo bảo vệ.                                                             | Đang chờ `@vuong123s` review & approve PR |

### Checklist dành cho Peer Reviewer (`@vuong123s`)

- [ ] Mọi số liệu trong Phần F và Phần H khớp với `test_parsers.py`, `docs/pbt-04-cycle-3-evidence.md` và artifact `pbt-04-evidence`.
- [ ] Lệnh tái lập máy sạch từ baseline `b29fec117053637428a935d43af16d9e1d65c1fb` và `scripts/demo-pbt-04.sh` chạy xanh trên `Coursework CI` (`ubuntu-latest`).
- [ ] Giải thích rõ 4 trọng tâm: platform MIME aliases, case-insensitive membership, registry/default consistency và 2 nhánh fallback.
- [ ] Tỷ lệ coverage toàn module (`45%`) được tách bạch rõ ràng với coverage mục tiêu của 4 helper (`21/21` dòng, `10/10` nhánh).
- [ ] Kịch bản demo 3–5 phút nêu đủ điều kiện tiên quyết, lệnh chạy, đầu ra kỳ vọng và phương án dự phòng.
- [ ] Toàn bộ góp ý review (nếu có) được giải quyết và các check CI (`Coursework CI`, `Lint`, `Documentation`) xanh trước khi merge vào `dev`.
