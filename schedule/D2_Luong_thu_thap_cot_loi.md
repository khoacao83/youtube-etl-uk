# Day 2 — Luồng thu thập cốt lõi

> Thuộc kế hoạch `Big_Project_YouTube_ETL_Top_100_UK_v2.md`. File này mô tả chi tiết việc cần làm trong ngày 2, kèm input, output và tiêu chí hoàn thành của từng việc.

## Tổng quan ngày

| Mục | Nội dung |
|---|---|
| Mục tiêu | Có pipeline video, stats và comment tầng A chạy thật; đếm quota; ghi theo transaction; hoàn tất phân loại kênh cho 100 nghệ sĩ |
| Input đầu ngày | Bàn giao D1: repo, `clean.artists` 100 dòng, ≥ 30 kênh `VERIFIED`, `api.py`/`warehouse.py` tối thiểu, tham số retention |
| Outcome cuối ngày | 3 nghệ sĩ có video, stats, comment thật trong BigQuery; chạy lại không nhân bản; mỗi run ghi số unit theo endpoint; 100 nghệ sĩ đều có trạng thái kênh |
| Quota dự kiến | 500–1.500 unit (test 1 và 3 nghệ sĩ, chọn nghệ sĩ ít video) |
| Thời lượng | ~9 giờ |

## Lịch gợi ý

| Khung giờ | Việc |
|---|---|
| 08:30–10:00 | 2.1 `config`, `api` (retry, đếm unit), `quota` |
| 10:00–11:00 | 2.2 `warehouse`: load job và transaction |
| 11:00–11:45 | 2.3 Schema `002` và `003` |
| 11:45–12:15 | 2.4 Khung `runner` và `pipeline_runs` |
| 13:15–14:45 | 2.5 Pipeline videos |
| 14:45–15:30 | 2.6 Pipeline stats |
| 15:30–16:45 | 2.7 Pipeline comments tầng A |
| 16:45–17:45 | 2.8 Test 1 → 3 nghệ sĩ, test idempotent |
| Xen kẽ cả ngày | 2.9 Hoàn tất phân loại kênh 100 nghệ sĩ |
| 17:45–18:15 | 2.10 Commit, log, bàn giao |

---

## Task 2.1 — `config.py`, `api.py`, `quota.py`

**Input:** `.env.example`, `api.py` tối thiểu từ D1.

**Các bước**

1. `config.py` dùng `pydantic-settings` đọc biến môi trường. Có `ENV=dev|prod`, tên dataset suy từ `ENV`, validate các trần quota.
2. `api.py`:
   - Bảng `UNIT_COST = {"channels.list":1, "playlistItems.list":1, "videos.list":1, "commentThreads.list":1, "comments.list":1, "search.list":100}`.
   - Mọi lệnh đi qua một hàm `call(endpoint, **params)` để:
     - Trước khi gọi: hỏi `QuotaBudget.can_spend(endpoint)`. Không đủ thì raise `BudgetExhausted`.
     - Gọi API với timeout 30 giây.
     - Phân loại lỗi:
       - 403 `quotaExceeded` hoặc `dailyLimitExceeded` → `QuotaExceeded`, không retry.
       - 403 `commentsDisabled` → `CommentsDisabled`.
       - 404 hoặc `videoNotFound` → `NotFound`.
       - 429 và 5xx → retry tối đa 5 lần, exponential backoff có jitter (`tenacity`).
     - Sau khi gọi: ghi nhận unit, sinh `request_id`, trả response kèm metadata.
3. `quota.py`:
   - `quota_day(now_utc)`: chuyển sang `America/Los_Angeles` và lấy ngày.
   - `QuotaBudget`: đọc tổng unit đã dùng trong `quota_day` từ `raw.pipeline_runs`, tính `run_cap = min(45% limit, 90% limit − đã dùng)`. Có ngân sách con theo task và trần riêng cho search.
4. Unit test với mock: đúng phân loại lỗi, đúng tính `quota_day` quanh mốc 0h Pacific, ngân sách không âm.

**Output:** ba module có test.

**Done khi**
- `pytest tests/test_api.py tests/test_quota.py` xanh.
- Test `quota_day` có case 14:59 và 15:01 giờ Việt Nam vào tháng 11 cho hai ngày quota khác nhau.

---

## Task 2.2 — `warehouse.py`: load job và transaction

**Input:** `warehouse.py` tối thiểu.

**Các bước**

1. `load_rows(table, rows, run_id, batch_id)`: load job JSON, `WRITE_APPEND`, schema tường minh, chờ job xong và kiểm tra lỗi.
2. `commit_batch(merge_sqls: list[str], params)`: ghép các câu lệnh thành một script
   ```sql
   BEGIN TRANSACTION;
   <merge 1>;
   <merge 2 - checkpoint>;
   COMMIT TRANSACTION;
   ```
   Chạy như một query job. Lỗi thì BigQuery tự rollback, hàm raise lỗi.
3. Mọi MERGE lọc staging theo `run_id` và `batch_id` để không đụng dữ liệu batch khác.
4. Test tích hợp (chạy với dataset dev, đánh dấu `@pytest.mark.integration`): cố tình làm câu MERGE thứ hai lỗi và xác nhận câu thứ nhất không được commit.

**Output:** `warehouse.py` hoàn chỉnh, test rollback.

**Done khi**
- Test rollback pass: bảng clean không đổi sau batch lỗi.

---

## Task 2.3 — Schema `002` và `003`

**Input:** mục 7 của kế hoạch v2, tham số retention từ D1.

**Các bước**

1. `002_video_comments_stats.sql`:
   - `clean.videos`: `video_id`, `artist_id`, `channel_id`, `title`, `published_at`, `duration_seconds`, `video_type`, `live_broadcast_content`, `is_available`, `last_checked_at`, `removed_at`, trường audit. Cluster `artist_id, channel_id`.
   - `clean.video_stats_history`: `video_id`, `artist_id`, `snapshot_date`, `snapshot_ts`, `view_count`, `like_count`, `comment_count`, `run_id`. Partition `snapshot_date`, cluster `artist_id, video_id`.
   - `clean.comments`: `comment_id`, `video_id`, `artist_id`, `parent_comment_id`, `is_reply`, `text_original`, `author_hash`, `like_count`, `published_at`, `updated_at`, `sample_mode`, trường audit. Partition `DATE(published_at)`, cluster `video_id`.
   - `clean.video_comment_status`: `video_id`, `comment_fetch_status`, `threads_fetched`, `replies_fetched`, `comment_count_at_fetch`, `last_fetched_at`.
   - Staging tương ứng trong raw, expiration 7 ngày.
2. `003_runs_checkpoints_candidates.sql`:
   - `raw.api_responses` (partition theo ngày, expiration theo `RAW_RETENTION_DAYS`).
   - `raw.pipeline_runs`: `run_id`, `env`, `trigger` (`timer`/`manual`), `started_at`, `ended_at`, `status`, `quota_day`, `snapshot_date`, `units_by_endpoint` (JSON), `units_total`, `rows_by_table` (JSON), `errors_by_type` (JSON), `backlog` (JSON), `git_commit`.
   - `raw.pipeline_checkpoints`: `task_type`, `entity_id`, `watermark`, `page_token`, `status`, `last_error`, `updated_run_id`, `updated_at`.
   - `raw.channel_candidates` (dùng ở D3).
3. Chạy `python -m youtube_etl init-schema` cho cả ba file. Lệnh phải chạy lại được (`CREATE TABLE IF NOT EXISTS`).

**Output:** toàn bộ bảng đã tạo.

**Done khi**
- `bq ls` của hai dataset đủ bảng theo mục 7.
- `init-schema` chạy hai lần không lỗi.

---

## Task 2.4 — Khung `runner.py`

**Các bước**

1. Sinh `run_id = <UTC yyyymmddTHHMMSSZ>-<6 ký tự ngẫu nhiên>`.
2. Tính `snapshot_date` (UTC) và `quota_day` **một lần** khi khởi động.
3. Ghi `RUNNING` vào `pipeline_runs`, kèm `git_commit` (`git rev-parse HEAD`).
4. Chạy các task theo cờ `--task`. Ở D2 chỉ có `videos`, `stats`, `comments`.
5. Bắt `BudgetExhausted` và `QuotaExceeded` → `DEFERRED`. Lỗi khác không bắt được → `FAILED`. Còn lại → `SUCCESS`.
6. Cuối run cập nhật `pipeline_runs` (unit, dòng, lỗi, backlog).
7. Log JSON từng dòng ra stdout, mỗi dòng có `run_id`, `task`, `artist_id`, `event`.

**Done khi**
- `python -m youtube_etl run --task stats --max-artists 0` tạo một dòng `SUCCESS` với 0 unit.

---

## Task 2.5 — Pipeline videos

**Input:** kênh `VERIFIED` có `uploads_playlist_id`.

**Các bước**

1. Với mỗi kênh, đọc checkpoint `task_type=videos_new` và `videos_backlog`.
2. **Video mới:** gọi `playlistItems.list` (`maxResults=50`) từ đầu playlist. Gom `video_id` và dừng khi gặp ID đã có trong `clean.videos`.
3. **Backlog:** tiếp tục từ `page_token` trong checkpoint, tối đa `N` trang mỗi run (cờ `--max-backlog-pages`, mặc định 5 ở D2).
4. Gọi `videos.list` theo lô 50 ID với `part=snippet,contentDetails,statistics,liveStreamingDetails`.
5. Suy ra `video_type`:
   - Có `liveStreamingDetails` → `LIVE` hoặc `PREMIERE`.
   - `duration` ≤ 180 giây và khung dọc nếu xác định được → `SHORT`. Nếu không xác định được hướng khung, ghi `SHORT_CANDIDATE` và nêu là hạn chế.
   - Còn lại → `REGULAR`.
6. Mỗi batch: load raw và staging, rồi `commit_batch` với MERGE `clean.videos` và MERGE checkpoint (`newest_video_id`, `page_token`, `backlog_done`).
7. Vì đã có `statistics` trong response, ghi luôn vào staging stats để pipeline stats không phải gọi lại cho video vừa lấy.

**Output:** `clean.videos` có video của nghệ sĩ test, checkpoint theo kênh.

**Done khi**
- Số video với `backlog_done = true` khớp `statistics.videoCount` của kênh (sai lệch nhỏ do video private hoặc bị gỡ được chấp nhận và ghi lại).

---

## Task 2.6 — Pipeline stats

**Các bước**

1. Lấy danh sách video `is_available = true` **chưa có snapshot** cho `snapshot_date` của run.
2. Gọi `videos.list(part=statistics)` theo lô 50.
3. MERGE vào `clean.video_stats_history` với `INSERT WHEN NOT MATCHED` (ghi lần đầu thắng).
4. ID không có trong response thì đánh dấu `is_available = false`, ghi `removed_at`.
5. Checkpoint `stats` theo kênh: `last_snapshot_date`.

**Done khi**
- Chạy stats hai lần trong cùng ngày UTC: lần hai tốn 0 unit (không còn video thiếu snapshot) và số dòng không đổi.

---

## Task 2.7 — Pipeline comments tầng A

**Input:** video có `published_at` trong 30 ngày.

**Các bước**

1. Với mỗi video, đọc checkpoint `comments_a`.
2. Gọi `commentThreads.list` với `part=snippet,replies`, `order=time`, `maxResults=100`, `textFormat=plainText`.
3. Dừng khi:
   - gặp thread có `published_at` ≤ watermark, hoặc
   - hết trang, hoặc
   - đạt 20 trang trong run (→ `PARTIAL_CAPPED`, lưu `page_token`).
4. Reply: nếu `totalReplyCount` > số reply đính kèm thì gọi `comments.list(parentId=..., maxResults=100)`, tối đa 2 trang.
5. Hash tác giả: `author_hash = sha256(salt + authorChannelId)`. Không lưu `authorProfileImageUrl`.
6. Xử lý trạng thái:
   - `CommentsDisabled` → `DISABLED`.
   - Trang đầu rỗng → `NO_COMMENTS`.
   - `BudgetExhausted` → `DEFERRED_QUOTA`, giữ checkpoint cũ.
   - Lỗi khác sau retry → `ERROR`.
7. Mỗi batch: MERGE `clean.comments`, MERGE `clean.video_comment_status`, MERGE checkpoint trong một transaction. Watermark là `published_at` lớn nhất **đã commit**.

**Done khi**
- Comment reply có `parent_comment_id` tồn tại trong bảng.
- Video tắt comment có trạng thái `DISABLED`, không làm run `FAILED`.

---

## Task 2.8 — Test 1 → 3 nghệ sĩ và test idempotent

**Chọn nghệ sĩ test:** 1 nghệ sĩ ít video (< 200), rồi thêm 2 nghệ sĩ có số video khác nhau. Ghi lý do chọn.

**Các bước**

1. `python -m youtube_etl run --env dev --artist-id <A>`, rồi kiểm tra BigQuery.
2. `python -m youtube_etl run --env dev --artist-id <A>,<B>,<C>`.
3. **Test idempotent:** chạy lại y hệt lệnh bước 2, rồi so sánh:
   ```sql
   SELECT 'videos', COUNT(*), COUNT(DISTINCT video_id) FROM clean.videos
   UNION ALL SELECT 'comments', COUNT(*), COUNT(DISTINCT comment_id) FROM clean.comments
   UNION ALL SELECT 'stats', COUNT(*), COUNT(DISTINCT CONCAT(video_id, CAST(snapshot_date AS STRING))) FROM clean.video_stats_history;
   ```
   Hai cột đếm phải bằng nhau, và số dòng sau lần chạy thứ hai chỉ tăng ở comment mới thật sự.
4. Chạy SQL liên kết: video không có artist hoặc channel tương ứng phải ra 0.
5. Lưu log hai lần chạy vào `docs/evidence/d2_run_<run_id>.log`.

**Output:** dữ liệu thật của 3 nghệ sĩ, log, kết quả truy vấn.

**Done khi**
- 3 nghệ sĩ có video, stats hôm nay và comment (hoặc trạng thái comment hợp lệ).
- Không trùng khóa. Lần chạy lại chỉ tốn unit cho phần thực sự mới.
- `pipeline_runs` có `units_by_endpoint` khớp với số lệnh trong log.

---

## Task 2.9 — Hoàn tất phân loại kênh cho 100 nghệ sĩ

**Các bước**

1. Tiếp tục T1/T2 cho các nghệ sĩ còn lại.
2. Cuối ngày, mọi nghệ sĩ phải ở một trong các trạng thái `VERIFIED`, `PENDING_REVIEW` hoặc `NEEDS_DISCOVERY`.
3. Nạp lại `clean.artist_channels`.

**Done khi**
- Truy vấn sau trả 0:
  ```sql
  SELECT COUNT(*) FROM clean.artists a
  LEFT JOIN clean.artist_channels c USING (artist_id)
  WHERE c.artist_id IS NULL;
  ```
- Mục tiêu: ≥ 85 nghệ sĩ `VERIFIED`. Các nghệ sĩ còn lại có `notes` giải thích.

---

## Task 2.10 — Commit và bàn giao

- Commit, push, CI xanh.
- `daily_log.md` mục D2: số video, comment, stats của 3 nghệ sĩ; unit đã dùng; số kênh theo trạng thái; lỗi gặp phải.

---

## Checklist cuối ngày D2

- [ ] `api.py` đếm unit, phân loại lỗi, retry; `quota.py` có test mốc Pacific
- [ ] Transaction MERGE + checkpoint có test rollback
- [ ] Schema `002`, `003` đủ bảng
- [ ] Runner ghi `pipeline_runs` đầy đủ
- [ ] Videos, stats, comments A chạy thật cho 3 nghệ sĩ
- [ ] Chạy lại không nhân bản (có truy vấn làm bằng chứng)
- [ ] 100 nghệ sĩ có trạng thái kênh, ≥ 85 `VERIFIED`
- [ ] `daily_log.md` D2 và commit hash

## Rủi ro trong ngày và cách xử lý

| Rủi ro | Xử lý |
|---|---|
| Transaction BigQuery chậm với batch nhỏ | Tăng kích thước batch lên 200–500 video |
| Nghệ sĩ test có quá nhiều comment | Trần 20 trang/video đã giới hạn; giảm bằng cờ khi test |
| Xác định Shorts không chính xác | Dùng `SHORT_CANDIDATE` và ghi hạn chế, không chặn tiến độ |
| Map kênh chưa đủ 85 | Chuyển phần thiếu sang `NEEDS_DISCOVERY` cho kênh phụ D3 xử lý |

## Bàn giao sang D3

- Input cho D3: ba pipeline chạy được; schema đầy đủ; số unit thật của 3 nghệ sĩ; danh sách nghệ sĩ `NEEDS_DISCOVERY` và `PENDING_REVIEW`; commit hash.
