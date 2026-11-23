# Day 1 — Nền móng và danh mục

> Thuộc kế hoạch `Big_Project_YouTube_ETL_Top_100_UK_v2.md`. File này mô tả chi tiết việc cần làm trong ngày 1, kèm input, output và tiêu chí hoàn thành của từng việc.

## Tổng quan ngày

| Mục | Nội dung |
|---|---|
| Mục tiêu | Có repo mới, GCP project mới, BigQuery schema nền, danh mục Top 100 trong BigQuery và bắt đầu map kênh |
| Input đầu ngày | Tài khoản Google có quyền tạo project và billing account; máy local có Python ≥ 3.11, `git`, `gcloud`, `bq`; tài khoản GitHub |
| Outcome cuối ngày | 100 nghệ sĩ trong `clean.artists`; ít nhất 30 kênh `VERIFIED`; một API request và một BigQuery load + MERGE thành công; tóm tắt chính sách lưu trữ trong README |
| Quota dự kiến | < 200 unit (chỉ `channels.list`) |
| Thời lượng | ~8–9 giờ làm việc |

## Lịch gợi ý

| Khung giờ | Việc |
|---|---|
| 08:30–09:30 | 1.1 Repo và môi trường Python |
| 09:30–11:00 | 1.2 GCP project, API, key, secret, service account, dataset |
| 11:00–11:30 | 1.3 Đọc Developer Policies, chốt quyết định lưu trữ |
| 11:30–13:00 | 1.4 Chốt tuần chart và chuẩn hóa `artists.csv` |
| 14:00–15:00 | 1.5 Schema `001` và nạp `clean.artists` |
| 15:00–15:30 | 1.6 Smoke test API + BigQuery |
| 15:30–18:00 | 1.7 Map kênh T1/T2 (tiếp tục sang D2) |
| 18:00–18:30 | 1.8 Commit, ghi nhật ký, bàn giao |

---

## Task 1.1 — Khởi tạo repository và môi trường

**Input:** tài khoản GitHub, Python ≥ 3.11.

**Các bước**

1. Tạo repo `youtube-etl-uk` trên GitHub (private), clone về máy.
2. Tạo cấu trúc thư mục theo mục 6 của kế hoạch v2, các file Python để trống có docstring.
3. Tạo môi trường ảo và dependency:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install google-api-python-client google-cloud-bigquery google-cloud-secret-manager \
               python-dotenv pydantic-settings tenacity pytest
   pip freeze > requirements.txt
   ```
4. `pyproject.toml` khai báo package `youtube_etl` trong `src/`, entry `python -m youtube_etl`.
5. `.gitignore`: `.venv/`, `.env`, `__pycache__/`, `*.json` chứa key, `output/`.
6. `.env.example` liệt kê đủ biến, không có giá trị thật:
   ```text
   ENV=dev
   GCP_PROJECT=
   BQ_LOCATION=asia-southeast1
   BQ_RAW_DATASET=yt_uk_dev_raw
   BQ_CLEAN_DATASET=yt_uk_dev_clean
   YOUTUBE_API_KEY_SECRET=projects/<project>/secrets/youtube-api-key/versions/latest
   QUOTA_DAILY_LIMIT=10000
   QUOTA_RESERVE_PCT=10
   QUOTA_RUN_CAP_PCT=45
   SEARCH_FALLBACK_ENABLED=true
   SEARCH_DAILY_UNIT_CAP=1000
   SEARCH_MAX_CALLS_PER_ARTIST=2
   SEARCH_COOLDOWN_DAYS=7
   ```
7. CI cơ bản (GitHub Actions) chạy `pytest` ở chế độ offline, không gọi API.

**Output**
- Repo có commit đầu tiên với cấu trúc thư mục, `requirements.txt`, `.env.example`, `.gitignore`, workflow CI.

**Done khi**
- `python -m youtube_etl --help` chạy được (in usage tạm).
- CI xanh với một test giả.
- `git log` không chứa secret nào.

---

## Task 1.2 — GCP project, API, secret, service account, dataset

**Input:** billing account ID, `gcloud` đã đăng nhập.

**Các bước**

1. Tạo project và gắn billing:
   ```bash
   gcloud projects create yt-uk-etl-<suffix> --name="YouTube ETL UK"
   gcloud config set project yt-uk-etl-<suffix>
   gcloud billing projects link yt-uk-etl-<suffix> --billing-account=<BILLING_ID>
   ```
2. Bật API:
   ```bash
   gcloud services enable youtube.googleapis.com bigquery.googleapis.com \
     secretmanager.googleapis.com compute.googleapis.com logging.googleapis.com \
     apikeys.googleapis.com
   ```
3. Tạo API key chỉ dùng được cho YouTube Data API v3 và lưu vào Secret Manager:
   ```bash
   gcloud services api-keys create --display-name="yt-etl-key" \
     --api-target=service=youtube.googleapis.com
   # lấy keyString từ output, rồi:
   printf '%s' '<KEY>' | gcloud secrets create youtube-api-key --data-file=-
   ```
4. Tạo service account cho VM:
   ```bash
   gcloud iam service-accounts create yt-etl-runner --display-name="YouTube ETL runner"
   SA=yt-etl-runner@yt-uk-etl-<suffix>.iam.gserviceaccount.com
   gcloud projects add-iam-policy-binding yt-uk-etl-<suffix> --member=serviceAccount:$SA --role=roles/bigquery.jobUser
   gcloud projects add-iam-policy-binding yt-uk-etl-<suffix> --member=serviceAccount:$SA --role=roles/logging.logWriter
   gcloud secrets add-iam-policy-binding youtube-api-key --member=serviceAccount:$SA --role=roles/secretmanager.secretAccessor
   ```
5. Tạo dataset cùng location (`asia-southeast1`), rồi cấp quyền ở cấp dataset bằng SQL:
   ```bash
   bq --location=asia-southeast1 mk --dataset yt-uk-etl-<suffix>:yt_uk_dev_raw
   bq --location=asia-southeast1 mk --dataset yt-uk-etl-<suffix>:yt_uk_dev_clean
   ```
   ```sql
   GRANT `roles/bigquery.dataEditor` ON SCHEMA yt_uk_dev_raw   TO "serviceAccount:<SA>";
   GRANT `roles/bigquery.dataEditor` ON SCHEMA yt_uk_dev_clean TO "serviceAccount:<SA>";
   ```
6. Cấu hình xác thực local: `gcloud auth application-default login`.
7. Ghi lại quota hiện tại của YouTube Data API v3 trong Console (APIs & Services → Quotas) và chụp ảnh.

**Output**
- Project, 6 API đã bật, secret `youtube-api-key`, service account `yt-etl-runner` với 4 quyền, hai dataset.
- Ảnh chụp: danh sách API đã bật, trang quota, danh sách dataset.

**Done khi**
- `gcloud secrets versions access latest --secret=youtube-api-key` trả key (từ máy local).
- `bq ls` thấy hai dataset.
- Key không xuất hiện trong repo hay lịch sử shell được commit.

---

## Task 1.3 — Đọc Developer Policies và chốt quyết định lưu trữ

**Input:** [YouTube API Services Developer Policies](https://developers.google.com/youtube/terms/developer-policies).

**Các bước**

1. Đọc phần về lưu trữ, làm mới và xóa API data, gồm cả quy định về thống kê lịch sử (metrics) và dữ liệu người dùng (comment, tác giả).
2. Trả lời và ghi vào `docs/data_retention.md`:
   - Thời hạn tối đa được giữ dữ liệu không làm mới là bao lâu?
   - `video_stats_history` được giữ bao lâu? Có cần cơ chế riêng không?
   - Comment và thông tin tác giả cần làm mới hay xóa khi nào?
   - Khi video hoặc kênh bị gỡ thì phải xử lý thế nào?
3. Chuyển các câu trả lời thành tham số cấu hình: `RAW_RETENTION_DAYS`, `STATS_RETENTION_DAYS`, `COMMENT_RETENTION_DAYS`, `REFRESH_AFTER_DAYS`.
4. Quyết định cách lưu tác giả comment: lưu `author_channel_id` dạng hash SHA-256 có salt và không lưu ảnh đại diện.

**Output**
- `docs/data_retention.md` có trích dẫn mục chính sách và quyết định tương ứng.
- Các tham số retention đã thêm vào `.env.example`.

**Done khi**
- Mọi bảng trong mục 7 của kế hoạch có thời hạn lưu được ghi rõ, hoặc ghi "không giới hạn" kèm lý do.

---

## Task 1.4 — Chốt tuần chart và chuẩn hóa `artists.csv`

**Input:** trang [YouTube Charts UK Weekly Top Artists](https://charts.youtube.com/charts/TopArtists/gb/weekly).

**Các bước**

1. Chọn tuần đã kết thúc gần nhất. Ghi `chart_week_start` và `chart_week_end`.
2. Chụp ảnh toàn trang chart (có tuần hiển thị) và lưu vào `docs/evidence/chart_<week>.png`.
3. Dùng nút tải xuống của chart. Lưu file gốc nguyên trạng vào `data/source/chart_<week>_raw.csv` và không sửa file này.
4. Viết `pipelines/catalogue.py::normalize_chart()`:
   - Đọc file gốc, giữ `rank` và `artist_name`.
   - Sinh `artist_id = uk-<week>-<rank 3 chữ số>-<slug tên>`.
   - Thêm `chart_week_start`, `chart_week_end`, `source_url`, `fetched_at` (UTC, ISO 8601), `chart_artist_url` nếu có.
   - Ghi `data/artists.csv`.
5. Viết kiểm tra tự động (`tests/test_catalogue.py`):
   - Đúng 100 dòng.
   - `rank` là tập {1..100}, không trùng.
   - `artist_id` không trùng.
   - Cảnh báo (không chặn) khi hai tên giống nhau sau khi chuẩn hóa (bỏ dấu, chữ thường).

**Output**
- `data/source/chart_<week>_raw.csv`, `data/artists.csv`, ảnh chart.
- Test catalogue đã pass.

**Done khi**
- `pytest tests/test_catalogue.py` xanh.
- Một người khác mở `artists.csv` và đối chiếu được 5 dòng ngẫu nhiên với ảnh chart.

**Nếu nút tải xuống không hoạt động:** sao chép thủ công 100 dòng từ trang và ghi `source_method = manual_copy` trong README. Ảnh chart là bằng chứng bắt buộc trong trường hợp này.

---

## Task 1.5 — Schema `001` và nạp `clean.artists`

**Input:** `data/artists.csv`, hai dataset.

**Các bước**

1. Viết `sql/001_schema.sql` tạo:
   - `clean.artists` (khóa `artist_id + chart_week_start`, cluster `artist_id`).
   - `clean.artist_channels` (khóa `artist_id + channel_id`).
   - `raw.staging_artists` và `raw.staging_artist_channels`, có expiration 7 ngày.
2. Mọi bảng clean có trường audit: `run_id`, `fetched_at`, `load_timestamp`.
3. Viết `warehouse.py` bản tối thiểu:
   - `apply_sql(path)`: chạy file SQL, thay `${RAW}` và `${CLEAN}` bằng tên dataset.
   - `load_rows(table, rows)`: load job từ JSON rows, `WRITE_APPEND`.
   - `merge(sql)`: chạy MERGE.
4. Lệnh `python -m youtube_etl init-schema` chạy `001`.
5. Lệnh `python -m youtube_etl load-catalogue`:
   - Load `artists.csv` vào staging với `run_id`.
   - MERGE vào `clean.artists`: cập nhật khi khớp, chèn khi chưa có.

**Output**
- Bảng đã tạo, `clean.artists` có 100 dòng.

**Done khi**
- Truy vấn sau trả `100, 1, 100, 100`:
  ```sql
  SELECT COUNT(*), MIN(rank), MAX(rank), COUNT(DISTINCT rank) FROM clean.artists;
  ```
- Chạy `load-catalogue` lần hai vẫn ra 100 dòng (idempotent).

---

## Task 1.6 — Smoke test API và BigQuery

**Input:** secret API key, `clean.artists`.

**Các bước**

1. `api.py` bản tối thiểu: lấy key từ Secret Manager, tạo client `youtube v3`, hàm `channels_list(ids=None, handle=None)`.
2. Gọi `channels.list` cho một kênh đã biết (ví dụ kênh của nghệ sĩ hạng 1), với `part=snippet,contentDetails,statistics`.
3. Ghi response vào `raw.api_responses` (tạo tạm bảng này nếu `003` chưa có) bằng load job.
4. In ra `uploads_playlist_id` lấy từ `contentDetails.relatedPlaylists.uploads`.

**Output**
- Log JSON của lệnh, một dòng trong `raw.api_responses`.

**Done khi**
- Có `uploads_playlist_id` hợp lệ (bắt đầu bằng `UU`).
- Dòng trong BigQuery có `run_id` khớp với log.
- Chụp ảnh log và truy vấn làm bằng chứng.

---

## Task 1.7 — Map kênh T1/T2 (bắt đầu)

**Input:** `data/artists.csv`, smoke test đã chạy.

**Các bước**

1. Tạo `data/artist_channels.csv` với đầy đủ cột theo mục 3.2 của kế hoạch.
2. Với mỗi nghệ sĩ, theo thứ tự rank:
   - **T1:** mở trang nghệ sĩ trên YouTube Charts (nếu có) hoặc website, mạng xã hội chính thức. Lấy link kênh YouTube và ghi `evidence_url`.
   - **T2:** đưa `channel_id` hoặc handle vào lệnh `python -m youtube_etl verify-channels`. Lệnh này gọi `channels.list` theo batch tối đa 50 ID, so tên kênh với tên nghệ sĩ, lấy `uploads_playlist_id`, số video và subscriber.
   - Gán `status`:
     - `VERIFIED`: có bằng chứng T1 và T2 khớp.
     - `PENDING_REVIEW`: có ứng viên nhưng chưa chắc (nhiều kênh, tên khác).
     - `NEEDS_DISCOVERY`: không tìm được ứng viên nào qua T1/T2.
   - Gán `channel_role`: `PRIMARY`, `VEVO` hoặc `SECONDARY`. Không đưa kênh "- Topic" vào.
3. Nạp kết quả vào `clean.artist_channels` (MERGE).

**Output**
- `artist_channels.csv` có ít nhất 30 nghệ sĩ `VERIFIED`, phần còn lại có trạng thái hoặc chưa xử lý.

**Done khi**
- Ít nhất 30 nghệ sĩ có kênh `VERIFIED` với `evidence_url` không rỗng.
- Truy vấn đếm theo `status` khớp với CSV.

**Ghi chú:** không chạy `search.list` trong D1. Nghệ sĩ không tìm được thì để `NEEDS_DISCOVERY`, kênh phụ sẽ xử lý từ D3.

---

## Task 1.8 — Commit và bàn giao

**Các bước**

1. Commit với message rõ ràng, push, kiểm tra CI xanh.
2. Viết `docs/daily_log.md` mục D1: việc đã xong, số liệu, quota đã dùng (xem trên Console), vướng mắc.
3. README phần đầu: mục tiêu, phạm vi, nguồn chart, tuần đã chốt, cách setup môi trường.

**Output:** commit hash cuối ngày, `daily_log.md`, README bản nháp.

---

## Checklist cuối ngày D1

- [ ] Repo có cấu trúc chuẩn, CI xanh, không có secret
- [ ] GCP project, 6 API, secret, service account, 2 dataset
- [ ] `docs/data_retention.md` có quyết định lưu trữ
- [ ] `artists.csv` 100 dòng, test pass, ảnh chart
- [ ] `clean.artists` = 100 dòng, nạp lại không trùng
- [ ] Smoke test API + BigQuery có bằng chứng
- [ ] ≥ 30 kênh `VERIFIED`
- [ ] `daily_log.md` D1 và commit hash

## Rủi ro trong ngày và cách xử lý

| Rủi ro | Xử lý |
|---|---|
| Chưa có billing hoặc project bị giới hạn tạo | Dùng project có sẵn nhưng mới hoàn toàn, ghi rõ trong README |
| Nút tải chart lỗi | Sao chép thủ công cộng ảnh chụp, ghi `source_method` |
| Quyền dataset bằng `GRANT` lỗi | Cấp `bigquery.dataEditor` qua Console ở cấp dataset |
| Map kênh chậm hơn dự kiến | Giữ mục tiêu 30, phần còn lại chuyển sang D2 (đã có trong kế hoạch) |

## Bàn giao sang D2

- Input cho D2: repo và commit hash, `clean.artists` 100 dòng, `clean.artist_channels` ≥ 30 `VERIFIED`, `warehouse.py` và `api.py` bản tối thiểu, tham số retention đã chốt.
