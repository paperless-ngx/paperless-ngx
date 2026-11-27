# PBT-05 Cycle 4: Báo cáo tổng kết, Hướng dẫn tái lập máy sạch & Kịch bản Demo bảo vệ

## Thông tin chung & Phân công

- **Issue**: [#52 — [Cycle 4][Bo] Final report & demo PBT-05 Parser selection](https://github.com/0Yaam/paperless-ngx/issues/52)
- **Người thực hiện (Owner)**: Phùng Nguyễn Hoài Bo (`@HubertPhung`, MSSV `2312585`)
- **Người review chéo (Peer Reviewer)**: Vũ Thế Huỳnh (`@1convitt`)
- **Suite**: `PBT-05` — Lựa chọn bộ phân tích tài liệu (`Parser Selection Rules`)
- **Hàm mục tiêu (Target)**: [`paperless.parsers.registry.ParserRegistry.get_parser_for_file`](../src/paperless/parsers/registry.py#L332-L407)
- **Baseline nhánh fork cố định**: `dev@b29fec117053637428a935d43af16d9e1d65c1fb` (mốc mở Cycle 4: `dev@0944d035255e9c6329ac74282661c9672240a5d5`)
- **Baseline upstream**: `da3de299f`
- **Tài liệu các Cycle trước**:
  - Thiết kế Cycle 1: [`pbt-05-parser-selection-design.md`](pbt-05-parser-selection-design.md)
  - PR triển khai Cycle 2: [#18](https://github.com/0Yaam/paperless-ngx/pull/18) (`925c1766c`)
  - Bằng chứng & RCA Cycle 3: [`pbt-05-cycle-3-evidence.md`](pbt-05-cycle-3-evidence.md) (PR [#47](https://github.com/0Yaam/paperless-ngx/pull/47) `b29fec117`)

---

## 1. Báo cáo tổng kết PBT-05 (Chuẩn cấu trúc Phần A–H)

### Phần A — Mục tiêu hệ thống & Ngữ cảnh luồng dữ liệu

Trong Paperless-ngx, tài liệu đi qua quy trình tiếp nhận (`documents.consumer` từ thư mục `consume/`, REST API `POST /api/documents/post_document/` và quy tắc email), sau đó được phân giải định dạng và trích xuất nội dung bởi các bộ phân tích (`DocumentParser` / `ParserProtocol`), lập chỉ mục tìm kiếm và lưu trữ.

Lớp `ParserRegistry` trong [`src/paperless/parsers/registry.py`](../src/paperless/parsers/registry.py#L151-L407) quản lý hai tập parser:

- `_builtins`: Các parser tích hợp sẵn của hệ thống (`TextDocumentParser`, `RemoteDocumentParser`, `TikaDocumentParser`, `MailDocumentParser`, `RasterisedDocumentParser`).
- `_external`: Các parser mở rộng do bên thứ ba cung cấp thông qua Python entry point nhóm `paperless_ngx.parsers`.

Hàm `ParserRegistry.get_parser_for_file(mime_type, filename, path=None, *, allow_remote=True)` đảm nhận nhiệm vụ quyết định chọn đúng một parser class cho từng tệp đầu vào (hoặc trả về `None` an toàn khi không có ứng viên hợp lệ). Báo cáo Cycle 4 tổng hợp chứng cứ chạy tất định, phạm vi bao phủ nhánh, hướng dẫn tái lập trên máy sạch và kịch bản demo bảo vệ cho thành phần này.

### Phần B — Kiến trúc & Cơ chế hoạt động của hàm mục tiêu

Hàm [`get_parser_for_file`](../src/paperless/parsers/registry.py#L332-L407) xử lý tuần tự qua từng ứng viên trong tuple `(*self._external, *self._builtins)`:

1. **Lọc theo định dạng MIME** (`L381–382`): Bỏ qua parser nếu `mime_type` không nằm trong từ điển `parser_class.supported_mime_types()`.
2. **Bảo vệ chế độ ngoại tuyến / cô lập** (`L384–389`): Khi `allow_remote=False`, loại bỏ mọi parser khai báo `getattr(parser_class, "uses_remote_service", False)` là `True`. Parser không khai báo thuộc tính này được coi là xử lý cục bộ.
3. **Chấm điểm ứng viên** (`L391–393`): Gọi `parser_class.score(mime_type, filename, path)`. Nếu trả về `None`, parser từ chối xử lý và bị bỏ qua (không đánh đồng `None` với điểm `0`).
4. **Chọn điểm cao nhất & ưu tiên external khi hòa** (`L395–397`): Cập nhật người thắng chỉ khi `best_score is None or score > best_score`. Vì danh sách `_external` được duyệt trước `_builtins` và dùng phép so sánh nghiêm ngặt `>`, parser mở rộng luôn giữ quyền ưu tiên khi bằng điểm với parser tích hợp sẵn.
5. **Ghi log truy vết & suy thoái an toàn** (`L399–407`): Nếu parser chiến thắng thuộc `_external`, hàm ghi log `INFO` thông tin gói mở rộng; nếu không có ứng viên nào hợp lệ, hàm trả về `None`.

### Phần C — Môi trường & Baseline đã kiểm chứng

- **Baseline nhánh fork cố định**: `dev@b29fec117053637428a935d43af16d9e1d65c1fb` (với bản mở Cycle 4 `dev@0944d035255e9c6329ac74282661c9672240a5d5` giữ nguyên toàn bộ mã nguồn và tệp test của PBT-05).
- **Môi trường Linux CI chuẩn hóa (`uv.lock`)**: Ubuntu Runner (`ubuntu-latest`), Python `3.12.16`, `pytest 9.1.1`, `hypothesis 6.168.5`, `pytest-cov 7.1.0`, `pytest-django 4.14.0`.
- **Cấu hình chạy tất định**:
  - `HYPOTHESIS_PROFILE=recorded` (`max_examples=250`, `deadline=None`, `suppress_health_check=[HealthCheck.function_scoped_fixture]`).
  - Hạt giống cố định: `--hypothesis-seed=20261008`, đơn luồng `-n 0`, bật đo nhánh `--cov=paperless.parsers.registry --cov-branch --cov-report=term-missing`.
  - Lưu ý hiển thị từ plugin: dòng header `pytest` có thể in `hypothesis profile 'ci'` theo thiết lập chung của `pyproject.toml`, nhưng từng hàm test trong [`test_parser_selection_pbt.py`](../src/paperless/tests/test_parser_selection_pbt.py#L36-L51) gắn trực tiếp decorator `@_pbt05_settings` theo biến môi trường `HYPOTHESIS_PROFILE=recorded`; phần `Hypothesis Statistics` xác nhận cả 7 hàm đều dừng tại `settings.max_examples=250`.
- **Các lần chạy GitHub Actions CI xác thực**:
  - Trên baseline `b29fec117`: [Coursework CI Run #45764068014](https://github.com/0Yaam/paperless-ngx/actions/runs/45764068014), job `PBT-05 Parser selection` — **success**, `7 passed in 20.63s`, artifact `pbt-05-evidence`.
  - Trên đầu nhánh `dev@0944d0352`: [Coursework CI Run #45791632304](https://github.com/0Yaam/paperless-ngx/actions/runs/45791632304), job `PBT-05 Parser selection` — **success**, `7 passed in 28.37s`, artifact `pbt-05-evidence`.
  - Đối chiếu Cycle 3 trước hợp nhất (`PR #41` gốc ghi trong [`pbt-05-cycle-3-evidence.md`](pbt-05-cycle-3-evidence.md)): [Coursework CI Run #45539433977](https://github.com/0Yaam/paperless-ngx/actions/runs/45539433977) (`7 passed in 32.16s`).

### Phần D — Cơ sở kỹ thuật K01 PBT, Phạm vi, Giả định & Tiêu chí Pass/Fail

- **Vì sao áp dụng Property-Based Testing (K01)**: Tập hợp các parser đăng ký có thể kết hợp tùy ý về số lượng (`1..8` parser), phân loại (`_external` hay `_builtins`), cờ mạng (`uses_remote_service`, `allow_remote`), tập MIME hỗ trợ và phân bố điểm (âm, `0`, dương, hoặc `None` từ chối). Kiểm thử theo ví dụ tĩnh khó bao quát hết các tổ hợp giao thoa giữa ưu tiên điểm, hòa điểm và loại trừ remote.
- **Giả định & Giới hạn phạm vi**:
  - Mỗi ca sinh tạo một `ParserRegistry()` hoàn toàn cô lập và các lớp `MockParser` nhẹ từ `MockParserSpec`, tránh phụ thuộc trạng thái singleton toàn cục `_registry` hay gói entry point ngoài hệ thống.
  - Bộ test chỉ kiểm chứng hợp đồng chọn parser của `get_parser_for_file`; việc nạp plugin qua `importlib.metadata.entry_points` (`discover`), `register_defaults()`, `log_summary()` và chạy trích xuất tài liệu thực tế (`parse()`) nằm ngoài phạm vi suite này (được cách ly khỏi `PBT-04` về ánh xạ MIME-extension tĩnh).
- **Tiêu chí Pass/Fail (Acceptance Gate)**:
  - Toàn bộ `7/7` hàm property trong `TestPbtParserSelection` đạt `PASSED`, không có ca `failing`.
  - Mỗi property trong `Hypothesis Statistics` đạt đủ `250 passing, 0 failing` (tổng `1,750` ca sinh hợp lệ kèm `10` ca `@example` biên cố định).
  - Độ bao phủ mục tiêu `ParserRegistry.get_parser_for_file` (`L332–407`) đạt **100% statement (`17/17`)** và **100% branch (`12/12`, `0` partial branch)**.

### Phần E — Mô hình 7 Property & Ma trận truy vết

Bộ test [`src/paperless/tests/test_parser_selection_pbt.py`](../src/paperless/tests/test_parser_selection_pbt.py#L92-L530) hiện thực đầy đủ 4 nhóm trọng tâm của suite: **thứ tự điểm**, **ưu tiên external khi hòa**, **loại trừ parser từ xa**, và **các trường hợp không chọn được parser**.

| Mã Invariant  | Tên hàm kiểm thử                                                        | Đầu vào / Strategy & `@example` biên                                                                                                      | Oracle kiểm chứng                                                                              |
| :------------ | :---------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------- |
| `PBT05-INV1`  | `test_highest_scoring_eligible_parser_wins`                             | `1..8` parser (`_external`/`_builtins`), MIME trong `MIME_POOL`, điểm `[-100, 100]` hoặc `None`, `uses_remote_service` & `allow_remote`   | Chọn đúng ứng viên hợp lệ có điểm lớn nhất; nếu tập hợp lệ rỗng thì trả về `None`              |
| `PBT05-INV2`  | `test_external_parser_wins_tie_with_builtin`                            | `1..4` external & `1..4` built-in cùng `target_mime` và cùng điểm hòa `[-50, 50]` (`@example` `tie_score=0`, `50`)                        | Kết quả thuộc `_external`, không thuộc `_builtins`, và là external parser đầu tiên theo thứ tự |
| `PBT05-INV3`  | `test_remote_parsers_excluded_when_not_allowed`                         | `1..3` remote parser điểm cao `[50, 100]` + `0..3` local parser `[-20, 40]` hoặc `None`; `allow_remote=False` (`@example` `[100]`/`[10]`) | Không bao giờ trả về parser có `uses_remote_service=True`; chọn local cao nhất hoặc `None`     |
| `PBT05-INV4A` | `test_none_returned_when_registry_is_empty`                             | Registry rỗng `0` parser, `target_mime`, `filename` bất kỳ, `allow_remote` boolean (`@example` `empty.pdf`)                               | Luôn trả về `None`, không phát sinh ngoại lệ truy cập danh sách rỗng                           |
| `PBT05-INV4B` | `test_none_returned_when_mime_unsupported_despite_valid_scores`         | `1..5` local parser điểm dương `[1, 100]` chỉ hỗ trợ `"other/unsupported-mime"`, truy vấn `target_mime` khác (`@example` điểm `80`)       | Luôn trả về `None`, không suy đoán theo phần mở rộng tên tệp                                   |
| `PBT05-INV4C` | `test_none_returned_when_matching_parsers_decline_with_none_score`      | `1..5` local parser khớp `"application/pdf"` nhưng toàn bộ trả về `score=None` (`@example` `"decliner"`)                                  | Luôn trả về `None`, không coi `None` là điểm `0`                                               |
| `PBT05-INV4D` | `test_none_returned_when_only_remote_parsers_available_and_not_allowed` | `1..5` parser khớp `"application/pdf"` điểm `[10, 100]`, đều có `uses_remote_service=True`, gọi với `allow_remote=False`                  | Luôn trả về `None`, tuyệt đối không nới lỏng để gửi tài liệu ra ngoài khi bị cấm               |

### Phần F — Tổng hợp kết quả chạy & Coverage

1. **Số liệu từ artifact Linux trên baseline `b29fec117` ([Run #45764068014](https://github.com/0Yaam/paperless-ngx/actions/runs/45764068014)) và `dev@0944d0352` ([Run #45791632304](https://github.com/0Yaam/paperless-ngx/actions/runs/45791632304))**:

   | Property                                                                | Passing | Failing | Invalid (Khử trùng) | Generate (Baseline `b29fec117`) | Generate (`dev@0944d0352`) | Trạng thái |
   | :---------------------------------------------------------------------- | ------: | ------: | ------------------: | ------------------------------: | -------------------------: | :--------: |
   | `test_highest_scoring_eligible_parser_wins`                             |     250 |       0 |                  27 |                          0.95 s |                     1.30 s |   PASSED   |
   | `test_external_parser_wins_tie_with_builtin`                            |     250 |       0 |                   0 |                          0.36 s |                     0.48 s |   PASSED   |
   | `test_remote_parsers_excluded_when_not_allowed`                         |     250 |       0 |                  98 |                          0.53 s |                     0.72 s |   PASSED   |
   | `test_none_returned_when_registry_is_empty`                             |     250 |       0 |                   0 |                          0.27 s |                     0.37 s |   PASSED   |
   | `test_none_returned_when_mime_unsupported_despite_valid_scores`         |     250 |       0 |                  39 |                          0.56 s |                     0.90 s |   PASSED   |
   | `test_none_returned_when_matching_parsers_decline_with_none_score`      |     250 |       0 |                  32 |                          0.50 s |                     0.68 s |   PASSED   |
   | `test_none_returned_when_only_remote_parsers_available_and_not_allowed` |     250 |       0 |                  35 |                          0.61 s |                     0.68 s |   PASSED   |
   | **Tổng cộng (`7` property + `10` `@example`)**                          |   1,750 |       0 |                 231 |                          3.78 s |                     5.13 s |  7/7 PASS  |
   - _(Ghi chú đối chiếu: Hai lần chạy CI tất định trên `b29fec117` và `0944d0352` cho số ca `invalid` giống hệt nhau `27 / 0 / 98 / 0 / 39 / 32 / 35`. Bản ghi trước đó ở PR #41 Run `#45539433977` trong [`pbt-05-cycle-3-evidence.md`](pbt-05-cycle-3-evidence.md) chạy trước khi bổ sung `-n 0` và tinh chỉnh suite nên ghi nhận bộ `invalid` là `23 / 0 / 85 / 0 / 77 / 24 / 33`; các ca `invalid` này chỉ là tổ hợp trùng lặp nội bộ bị Hypothesis loại trên miền chiến lược hữu hạn, không phải lỗi kiểm thử.)_
   - Phiên chạy đối chứng cục bộ trên Windows (Python `3.12.10`, pytest `9.2.0`, Hypothesis `6.170.17`, `--noconftest`) cũng đạt `7 passed in 12.94s`, `1,750` ca hợp lệ `passing` và `0` `failing`.

2. **Bằng chứng bao phủ câu lệnh và nhánh (`coverage.py --branch`)**:

   Trích nguyên văn dòng báo cáo của `src/paperless/parsers/registry.py` trong cả hai artifact `pbt-05-run.log` (`Run #45764068014` và `Run #45791632304`):

   ```text
   Name                                Stmts   Miss Branch BrPart  Cover   Missing
   -----------------------------------------------------------------------------------------------------------
   src/paperless/parsers/registry.py      89     47     28      0    46%   89-99, 118-122, 200-210, 234-259, 282-303, 326
   -----------------------------------------------------------------------------------------------------------
   ```

   - **Phạm vi toàn module (`46%`)**: Các dòng thiếu nằm ở `get_parser_registry` (`89–99`), `init_builtin_parsers` (`118–122`), `register_defaults` (`200–210`), `discover` (`234–259`), `log_summary` (`282–303`) và `all_parsers` (`326`) — đều nằm ngoài hợp đồng mục tiêu của PBT-05.
   - **Phạm vi hàm mục tiêu `ParserRegistry.get_parser_for_file` (`L332–407`)**: Đạt **17/17 dòng chạy (`100%` Statement Coverage)** (`[332, 375, 376, 380, 381, 382, 384, 389, 391, 392, 393, 395, 396, 397, 399, 400, 407]`) và **12/12 nhánh điều khiển (`100%` Branch Coverage, `0` partial/missing branches)**:
     - Vòng lặp `for parser_class in ...` (`380 -> 381` và kết thúc `380 -> 399`).
     - Lọc MIME (`381 -> 382` skip và `381 -> 384` pass).
     - Chốt chặn `allow_remote` (`384 -> 389` block và `384 -> 391` allow).
     - Từ chối điểm `None` (`392 -> 393` skip và `392 -> 395` pass).
     - Cập nhật điểm cao nhất (`395 -> 396` update và `395 -> 380` giữ nguyên).
     - Nhánh ghi log external (`399 -> 400` log external và `399 -> 407` trả kết quả trực tiếp).

### Phần G — Phân tích nguyên nhân gốc (No-Failure RCA), Kiểm chứng Mutation & Giới hạn

1. **RCA không lỗi ở sản phẩm (`No Production Defect`)**: Qua `1,750` ca ngẫu nhiên + `10` ca `@example` ở mỗi lần chạy, `get_parser_for_file` giữ vững toàn bộ 7 invariant nhờ ba quyết định thiết kế đúng trong [`registry.py`](../src/paperless/parsers/registry.py#L380-L398): (a) duyệt `_external` trước `_builtins`, (b) kiểm tra `score is None` tách biệt hoàn toàn với `score == 0` hay điểm âm, và (c) chỉ ghi đè ứng viên thắng bằng phép so sánh nghiêm ngặt `score > best_score`.
2. **Kiểm chứng khả năng phát hiện lỗi (Mutation & Shrinking Check)**: Chạy thử nghiệm tiêm lỗi trong bộ nhớ (không chỉnh sửa mã nguồn trong Git) trên suite hiện tại xác nhận:
   - **Đột biến 1 (sửa `score > best_score` thành `score >= best_score`)**: `test_external_parser_wins_tie_with_builtin` lập tức bắt được lỗi tại `assert result in registry._external` với ca biên `tie_score=50, ext_count=2, builtin_count=3, target_mime='image/png'` (cũng như `tie_score=0`).
   - **Đột biến 2 (bỏ chốt chặn `allow_remote` ở dòng `384`)**: `test_remote_parsers_excluded_when_not_allowed` lập tức thất bại tại `assert getattr(result, "uses_remote_service", False) is False` với ví dụ `remote_scores=[100], local_scores=[10], target_mime='application/pdf'` (và `PBT05-INV4D` cũng phát hiện qua `cloud_ocr`).
3. **Rủi ro tồn dư & giới hạn ngoài phạm vi**:
   - Hàm `get_parser_for_file` chưa bọc `try/except` quanh lời gọi `supported_mime_types()` và `score()` của plugin bên thứ ba; nếu một plugin ném ngoại lệ ở thời điểm chấm điểm, quá trình chọn parser cho tài liệu sẽ gián đoạn (trái với cách `discover()` bắt lỗi khi import). Đây là rủi ro tích hợp nằm ngoài hợp đồng selection hiện tại.
   - `discover()` và `register_builtin()` chưa kiểm tra trùng lặp class khi đăng ký nhiều lần, làm tăng số lượt chấm điểm lặp nhưng không sai kết quả chọn do dùng phép so sánh `>`.

### Phần H — Lưu cứng phiên bản & Danh mục truy vết

| Thành phần / Mốc đối chiếu          | Mã định danh / Đường dẫn                                                                                                                               | Ý nghĩa đối chiếu                                                                                             |
| :---------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------ |
| Baseline nhánh fork cố định         | `dev@b29fec117053637428a935d43af16d9e1d65c1fb`                                                                                                         | Mốc checkout sạch sau khi merge Cycle 3 của PBT-05 ([PR #47](https://github.com/0Yaam/paperless-ngx/pull/47)) |
| Commit mở Cycle 4                   | `dev@0944d035255e9c6329ac74282661c9672240a5d5`                                                                                                         | Mốc cập nhật README Cycle 4 giữ nguyên target & suite PBT-05                                                  |
| Kết quả Coursework CI (baseline)    | [Run #45764068014](https://github.com/0Yaam/paperless-ngx/actions/runs/45764068014)                                                                    | Chạy `PBT-05 Parser selection` trên `b29fec117` — `7 passed in 20.63s`                                        |
| Kết quả Coursework CI (trên `dev`)  | [Run #45791632304](https://github.com/0Yaam/paperless-ngx/actions/runs/45791632304)                                                                    | Chạy `PBT-05 Parser selection` trên `0944d0352` — `7 passed in 28.37s`                                        |
| Artifact log CI                     | `pbt-05-evidence` (`.artifacts/pbt-05-run.log`)                                                                                                        | Toàn văn output pytest, bảng branch coverage và Hypothesis Statistics                                         |
| Script tái lập & kiểm chứng tự động | [`scripts/demo-pbt-05.sh`](../scripts/demo-pbt-05.sh)                                                                                                  | Kiểm tra baseline, không drift mã nguồn, chạy pytest và xác minh coverage JSON                                |
| Mã nguồn mục tiêu & bộ kiểm thử     | [`registry.py`](../src/paperless/parsers/registry.py#L332-L407), [`test_parser_selection_pbt.py`](../src/paperless/tests/test_parser_selection_pbt.py) | Hàm sản phẩm và 7 property Hypothesis + 10 `@example`                                                         |

---

## 2. Hướng dẫn tái lập trên máy sạch (Clean-Machine Reproduction)

### Điều kiện tiên quyết

- Hệ điều hành: **Linux, macOS hoặc WSL2** (khuyến nghị cho môi trường chuẩn; tệp khóa `uv.lock` giới hạn một số wheel chỉ dành cho Linux/macOS).
- Công cụ: `git`, Astral `uv` (`0.12.x`), kết nối mạng cho lần đồng bộ gói đầu tiên.

### Các bước chạy lại từ bản checkout sạch (Linux / macOS / WSL2)

```bash
# 1. Clone mới repository và checkout đúng baseline Cycle 4
git clone --branch dev https://github.com/0Yaam/paperless-ngx.git
cd paperless-ngx
git checkout b29fec117053637428a935d43af16d9e1d65c1fb

# 2. Đồng bộ chính xác các gói kiểm thử từ uv.lock
uv sync --python 3.12 --group testing --frozen

# 3. Chạy bộ PBT-05 tất định với profile recorded và đo branch coverage
HYPOTHESIS_PROFILE=recorded uv run --python 3.12 --dev --frozen pytest \
  src/paperless/tests/test_parser_selection_pbt.py \
  -k TestPbtParserSelection -n 0 -v --hypothesis-seed=20261008 \
  --hypothesis-show-statistics --cov=paperless.parsers.registry \
  --cov-branch --cov-report=term-missing
```

### Chạy bằng script tự động trên nhánh `dev` cuối kỳ

Trên nhánh `dev` (hoặc WSL2/Ubuntu CI), chạy trực tiếp script đã khóa baseline:

```bash
bash scripts/demo-pbt-05.sh
```

Script tự động kiểm tra: (1) lịch sử kế thừa từ `b29fec117053637428a935d43af16d9e1d65c1fb`, (2) không có sai lệch mã nguồn ở `registry.py` và `test_parser_selection_pbt.py`, (3) đồng bộ `uv.lock`, (4) chạy `pytest` tất định, (5) xác nhận `7/7` property đạt `250 passing, 0 failing` và `17/17` dòng, `12/12` nhánh trong `get_parser_for_file`, đồng thời xuất artifact vào `.artifacts/pbt-05-cycle-4/` (`pbt-05-run.log`, `environment.txt`, `coverage.json`, `verification.json`).

### Đầu ra & Thống kê kỳ vọng

- **Pytest summary**: `7 passed` (`100%`).
- **Hypothesis Statistics**: Tất cả 7 hàm đạt `250 passing, 0 failing` (tổng `1,750` ca sinh hợp lệ); số ca invalid khử trùng lặp trên Linux `uv.lock` là `27 / 0 / 98 / 0 / 39 / 32 / 35`.
- **Coverage (`--cov-branch`)**: `src/paperless/parsers/registry.py` đạt `89 stmts, 47 miss, 28 branch, 0 BrPart, 46%`; các dòng missing chỉ nằm ngoài `L332–407`, tương ứng `17/17` dòng và `12/12` nhánh của `get_parser_for_file`.
- **Artifact trên GitHub Actions**: Workflow **Coursework CI** $\rightarrow$ job **PBT-05 Parser selection** $\rightarrow$ tải artifact **`pbt-05-evidence`**.

---

## 3. Kịch bản Demo bảo vệ cuối kỳ (3–5 phút)

Thực hiện tuần tự 4 bước sau khi bảo vệ mà không cần thiết lập ngầm ngoài tài liệu:

1. **Xác nhận baseline và tính toàn vẹn (30 giây)**:

   ```bash
   git rev-parse --short HEAD
   git diff --stat b29fec117053637428a935d43af16d9e1d65c1fb HEAD -- src/paperless/parsers/registry.py src/paperless/tests/test_parser_selection_pbt.py
   ```

   Kỳ vọng: lệnh `git diff --stat` không xuất ra biến đổi nào (mã nguồn mục tiêu và bộ test khớp 100% baseline).

2. **Chạy trực tiếp demo script và trình bày 4 nhóm tình huống (2 phút)**:

   ```bash
   bash scripts/demo-pbt-05.sh
   ```

   Giải thích trực tiếp trên output `pytest` và `verification.json` 4 nhóm trọng tâm của PBT-05:
   - **Thứ tự điểm (`Score ordering`)**: `test_highest_scoring_eligible_parser_wins` — điểm lớn nhất thắng kể cả `0` và số âm (`-1 > -100`).
   - **Ưu tiên mở rộng khi hòa (`External tie precedence`)**: `test_external_parser_wins_tie_with_builtin` — cùng điểm hòa (`0` hoặc `50`), parser trong `_external` luôn thắng `_builtins`.
   - **Loại trừ parser từ xa (`Remote exclusion`)**: `test_remote_parsers_excluded_when_not_allowed` — `allow_remote=False` chặn triệt để parser có `uses_remote_service=True` dù điểm cao nhất (`100`).
   - **4 trường hợp không chọn được parser (`No-selection cases`)**: registry rỗng (`INV4A`), không khớp MIME dù điểm cao (`INV4B`), mọi parser đều trả `score=None` (`INV4C`), chỉ có remote parser khi offline (`INV4D`).
   - Chỉ rõ `17/17` dòng và `12/12` nhánh mục tiêu trong `verification.json`.

3. **Minh họa khả năng bắt lỗi bằng Mutation Check (60 giây — tùy chọn)**:
   Trình bày nhanh kết quả thí nghiệm trong bộ nhớ (Phần G): khi đảo `>` thành `>=` hoặc bỏ kiểm tra `allow_remote`, bộ `@example` và property lập tức thất bại tại `test_external_parser_wins_tie_with_builtin` (`tie_score=50`) và `test_remote_parsers_excluded_when_not_allowed` (`remote_scores=[100], local_scores=[10]`).

4. **Phương án dự phòng khi Demo (Fallback)**:
   - **Tình huống A (Máy bảo vệ chỉ có Windows bản địa, không dùng được `uv.lock`)**: Chạy trong WSL2/Ubuntu hoặc chạy kiểm chứng độc lập không phụ thuộc `uv.lock` qua PowerShell (`PYTHONPATH=src`, `HYPOTHESIS_PROFILE=recorded`, `uv run --no-project --with pytest --with pytest-cov --with hypothesis --with django --with celery pytest --noconftest ...`) như đã xác thực đạt `7 passed in 12.94s`.
   - **Tình huống B (Mất mạng / không tải được dependency tại buổi bảo vệ)**: Mở trực tiếp tệp log `.artifacts/pbt-05-run.log` và `verification.json` đã tải sẵn từ artifact `pbt-05-evidence` của [Coursework CI Run #45764068014](https://github.com/0Yaam/paperless-ngx/actions/runs/45764068014) / [Run #45791632304](https://github.com/0Yaam/paperless-ngx/actions/runs/45791632304).

---

## 4. Bằng chứng Review chéo (Peer-Review Evidence) & Checklist nghiệm thu

### Lịch sử Review chéo qua các Cycle

| Giai đoạn | Pull Request / Issue                                                                                                            | Người review          | Nội dung góp ý & Chỉnh sửa                                                                                                                                                                                                                                                                                                      | Kết quả & Commit                                                        |
| :-------- | :------------------------------------------------------------------------------------------------------------------------------ | :-------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :---------------------------------------------------------------------- |
| Cycle 1–2 | [PR #18](https://github.com/0Yaam/paperless-ngx/pull/18)                                                                        | `@1convitt`, `@0Yaam` | `@1convitt` yêu cầu tách `test_ineligible_or_declining_parsers_return_none` thành 4 property `None` độc lập (`INV4A–4D`) và thêm `--hypothesis-seed=20261008`, `--hypothesis-show-statistics`, artifact log vào CI. Đã chỉnh sửa đầy đủ ở `33312fe5`.                                                                           | **`APPROVED`** (`@0Yaam`, `2026-10-12T21:13:53Z`), Đã merge `925c1766c` |
| Cycle 3   | [PR #41](https://github.com/0Yaam/paperless-ngx/pull/41) $\rightarrow$ [PR #47](https://github.com/0Yaam/paperless-ngx/pull/47) | `@0Yaam`              | Trên `PR #41` (`f8802f9a7`), `@0Yaam` xác nhận `7/7` property (`250` mẫu) pass trong artifact nhưng yêu cầu: (1) đồng bộ log & số liệu thật từ `45539433977`, (2) bật `--cov-branch` trong `coursework-ci.yml`, (3) bỏ các chỉnh sửa CI ngoài phạm vi (`ci-backend.yml`, `project-actions.yml`). Đã tách nhánh sạch ở `PR #47`. | Đã giải quyết & merge `b29fec117` (`2026-11-26T05:49:15Z`)              |
| Cycle 4   | Issue [#52](https://github.com/0Yaam/paperless-ngx/issues/52)                                                                   | `@1convitt`           | Tổng hợp báo cáo chuẩn A–H, bổ sung `scripts/demo-pbt-05.sh` gắn vào `Coursework CI`, hướng dẫn tái lập máy sạch, kịch bản demo bảo vệ và bảng truy vết review.                                                                                                                                                                 | Đang chờ `@1convitt` review & approve trên PR Cycle 4                   |

### Checklist dành cho Peer Reviewer (`@1convitt`)

- [ ] Mọi số liệu trong Phần F và Phần H khớp với `test_parser_selection_pbt.py`, `docs/pbt-05-cycle-3-evidence.md` và artifact CI `pbt-05-evidence` (`Run #45764068014` / `#45791632304`).
- [ ] Lệnh tái lập trên máy sạch từ baseline `b29fec117053637428a935d43af16d9e1d65c1fb` và `scripts/demo-pbt-05.sh` chạy xanh trên CI Linux.
- [ ] Độ bao phủ toàn module (`46%`) được phân tách rõ ràng với độ bao phủ của hàm mục tiêu `get_parser_for_file` (`17/17` dòng, `12/12` nhánh).
- [ ] Kịch bản demo 3–5 phút nêu đủ điều kiện tiên quyết, lệnh chạy, kết quả kỳ vọng (cả 4 nhóm trọng tâm) và phương án dự phòng.
- [ ] Toàn bộ góp ý review (nếu có) được xử lý và `Coursework CI`, `Lint`, `Documentation` xanh trước khi merge.
