# Day 4 — Nghiệm thu và hồ sơ

> Thuộc kế hoạch `Big_Project_YouTube_ETL_Top_100_UK_v2.md`. File này mô tả chi tiết việc cần làm trong ngày 4, kèm input, output và tiêu chí hoàn thành của từng việc.

## Tổng quan ngày

| Mục | Nội dung |
|---|---|
| Mục tiêu | Chứng minh hệ thống chạy tự động ở cả hai khung giờ, chất lượng dữ liệu đạt, có hồ sơ nộp bài đầy đủ với số liệu thật |
| Input đầu ngày | Bàn giao D3: commit trên VM, `run_id` lượt 23:00, số liệu 10 nghệ sĩ, ứng viên kênh chờ duyệt, danh sách lỗi mở |
| Outcome cuối ngày | Bằng chứng lượt 23:00 và 07:00; `quality_checks.sql` chạy với kết quả đã giải thích; bảng coverage và bảng quota thật; README hoàn chỉnh; báo cáo Word; commit cuối trên VM |
| Quota dự kiến | Lượt 07:00 dùng phần còn lại của ngày quota; ban ngày dùng rất ít (sửa lỗi dùng dev và `--max-units` nhỏ). Từ khoảng 15:00 sang ngày quota mới |
| Thời lượng | ~9 giờ, cộng lượt 23:00 của D4 nếu cần thêm bằng chứng |

## Lịch gợi ý

| Khung giờ | Việc |
|---|---|
| 07:00–07:45 | 4.1 Theo dõi lượt 07:00 |
| 08:30–09:30 | 4.2 Đối chiếu hai lượt theo `run_id` |
| 09:30–11:00 | 4.3 Chạy `quality_checks.sql` và giải thích kết quả |
| 11:00–11:45 | 4.4 Duyệt ứng viên kênh từ discovery |
| 11:45–13:30 | 4.5 Sửa lỗi, test dev, triển khai commit cuối |
| 14:30–15:30 | 4.6 Bảng coverage và bảng quota |
| 15:30–17:00 | 4.7 README hoàn chỉnh |
| 17:00–18:30 | 4.8 Báo cáo Word |
| 18:30–19:00 | 4.9 Thu bằng chứng, đóng gói hồ sơ |

---

## Task 4.1 — Theo dõi lượt 07:00

**Các bước**

1. Từ 07:00 theo dõi `journalctl -u youtube-etl.service -f`.
2. Xác nhận:
   - `snapshot_date` là ngày UTC mới. 07:00 ICT là 00:00 UTC, nên nếu log ghi ngày cũ thì đó là trường hợp khởi động sớm đã lường trước ở mục 9.2 của kế hoạch. Khi đó ghi nhận và kiểm tra lượt 23:00 D4 bù snapshot.
   - Lượt này ghi snapshot cho phần lớn video (lượt sở hữu snapshot của ngày UTC).
   - Tổng unit của lượt 23:00 hôm trước cộng lượt 07:00 ≤ 90% quota.
3. Lưu log vào `docs/evidence/run_0700_<date>.md`.

**Done khi**
- Có một run `trigger=timer` lúc 07:00 kết thúc `SUCCESS` hoặc `DEFERRED`.

---

## Task 4.2 — Đối chiếu hai lượt theo `run_id`

**Các bước**

1. Truy vấn hai run:
   ```sql
   SELECT run_id, trigger, status, quota_day, snapshot_date,
          started_at, ended_at, units_total, rows_by_table, errors_by_type, backlog, git_commit
   FROM raw.pipeline_runs
   WHERE trigger = 'timer'
   ORDER BY started_at DESC LIMIT 2;
   ```
2. Đối chiếu dòng dữ liệu với từng run:
   ```sql
   SELECT run_id, COUNT(*) FROM clean.video_stats_history
   WHERE run_id IN ('<run_2300>', '<run_0700>') GROUP BY run_id;
   -- lặp lại cho clean.videos, clean.comments
   ```
   Số dòng mỗi bảng phải khớp `rows_by_table` của run.
3. Đối chiếu log với BigQuery: `run_id`, thời gian bắt đầu/kết thúc, số unit.
4. Xác nhận cả hai run cùng `quota_day` và tổng unit nằm trong ngân sách.

**Output:** `docs/evidence/run_reconciliation.md` gồm bảng đối chiếu hai run.

**Done khi**
- Mọi số liệu trong log khớp BigQuery. Mọi chênh lệch đều có giải thích.

---

## Task 4.3 — Kiểm tra chất lượng

**Input:** `sql/quality_checks.sql`, viết theo mục 12 của kế hoạch.

**Các bước**

1. Hoàn thiện `quality_checks.sql`. Mỗi check trả một dòng gồm `check_name`, `expected`, `actual`, `status` (`PASS` / `WARN` / `FAIL`). Các nhóm check:

| Nhóm | Check |
|---|---|
| Danh mục | 100 nghệ sĩ; rank 1–100 không trùng; mọi nghệ sĩ có trạng thái kênh; kênh T3 có `evidence_url` |
| Khóa | Không trùng `video_id`, `comment_id`, `video_id + snapshot_date` |
| Liên kết | Không có video mồ côi; không có reply mồ côi; comment cấp đầu có `parent_comment_id` null |
| Checkpoint | Không có checkpoint trỏ tới dữ liệu chưa có trong clean |
| Run | Không có run `RUNNING` quá hạn; tổng unit mỗi `quota_day` ≤ 90%; search ≤ trần |
| Độ tươi | Giờ kể từ snapshot gần nhất; tỷ lệ video khả dụng có snapshot ngày UTC gần nhất |
| Độ phủ | Theo nghệ sĩ: video đã quét / `videoCount`; comment theo tầng A/B; phân bố `comment_fetch_status` |
| Công bằng | Nghệ sĩ có độ phủ thấp nhất so với trung vị (phát hiện bị bỏ đói quota) |

2. Chạy lệnh `python -m youtube_etl quality-check` và xuất kết quả ra `docs/evidence/quality_checks_<date>.csv`.
3. Với mỗi `WARN` hoặc `FAIL`: tìm nguyên nhân, sửa (task 4.5) hoặc ghi là hạn chế đã biết.

**Done khi**
- Không còn `FAIL` ở nhóm Khóa, Liên kết, Checkpoint.
- Mọi `WARN` có giải thích trong báo cáo.

---

## Task 4.4 — Duyệt ứng viên kênh từ discovery

**Các bước**

1. Liệt kê ứng viên:
   ```sql
   SELECT artist_id, channel_id, score, score_reasons
   FROM raw.channel_candidates
   WHERE status = 'PENDING_REVIEW'
   ORDER BY artist_id, score DESC;
   ```
2. Với mỗi nghệ sĩ, mở kênh ứng viên điểm cao nhất, đối chiếu với nguồn chính thức và lấy `evidence_url`.
3. Chấp nhận bằng `review-candidates --accept`, hoặc từ chối (`REJECTED`) kèm lý do.
4. Nạp lại `clean.artist_channels`. Kênh mới sẽ được thu thập từ lượt chạy kế tiếp.

**Output:** danh sách quyết định duyệt.

**Done khi**
- Không còn ứng viên `PENDING_REVIEW` chưa có quyết định, hoặc phần còn lại được ghi là backlog.
- Báo cáo nêu rõ số nghệ sĩ cần dùng `search.list`, số unit đã dùng và kết quả duyệt.

---

## Task 4.5 — Sửa lỗi và triển khai commit cuối

**Các bước**

1. Gom lỗi từ log 23:00 và 07:00, kết quả quality checks và danh sách lỗi mở từ D3.
2. Phân loại: phải sửa trước khi nộp / ghi là hạn chế.
3. Sửa trên local. Test offline, rồi chạy dataset dev với `--max-units` nhỏ.
4. Nếu thay đổi logic ghi dữ liệu: chạy lại test idempotent (task 2.8) trên dev.
5. Triển khai lên VM:
   ```bash
   sudo -u etl git -C /opt/youtube-etl-uk fetch
   sudo -u etl git -C /opt/youtube-etl-uk checkout <commit mới>
   sudo -u etl /opt/youtube-etl-uk/.venv/bin/pip install -e /opt/youtube-etl-uk
   ```
   Không sửa code trực tiếp trên VM.
6. Nếu cần bằng chứng sau khi sửa: chạy tay một lượt nhỏ trên VM, hoặc chờ lượt 23:00 D4.

**Done khi**
- `git_commit` trong run mới nhất trên VM bằng commit cuối trong repo.

---

## Task 4.6 — Bảng coverage và bảng quota

**Các bước**

1. Bảng coverage, trích bằng SQL và lưu thành CSV:

| Chỉ số | Giá trị |
|---|---|
| Nghệ sĩ trong danh mục | 100 |
| Nghệ sĩ có kênh `VERIFIED` (theo T1/T2/T3) | … |
| Kênh đã xác minh (gồm VEVO) | … |
| Video đã quét / tổng `videoCount` các kênh | … / … |
| Kênh đã xong backlog video | … |
| Video có snapshot ngày UTC gần nhất | … |
| Rows `video_stats_history` | … |
| Video đã lấy comment tầng A / tầng B | … / … |
| Comment đã thu (top-level / reply) | … / … |
| Video `DISABLED` / `NO_COMMENTS` / `DEFERRED_QUOTA` / `ERROR` / `PARTIAL_CAPPED` | … |
| Video bị gỡ (`is_available = false`) | … |
| Backlog còn lại (video, comment, discovery) | … |

2. Bảng quota theo `quota_day` và theo task/endpoint của mọi run, gồm cả test.
3. Ước tính số ngày cần để xong backlog video, dựa trên tốc độ thực tế của hai lượt tự động.

**Output:** `docs/evidence/coverage_<date>.csv`, `docs/evidence/quota_<date>.csv`.

**Done khi**
- Mọi số trong bảng lấy từ truy vấn, kèm truy vấn gốc trong `sql/reports/`.

---

## Task 4.7 — README hoàn chỉnh

**Nội dung bắt buộc**

1. Mục tiêu và câu phạm vi chuẩn: `Top 100 artists popular in the United Kingdom market, selected from YouTube Charts for one fixed weekly period`.
2. Nguồn chart, tuần đã chốt, cách lấy danh mục.
3. Kiến trúc (sơ đồ Mermaid) và luồng mỗi run.
4. Cách xác minh kênh ba tầng, chính sách VEVO/Topic, kênh phụ `search.list` và cách bật/tắt.
5. Ngân sách quota, thứ tự ưu tiên, chính sách lấy mẫu comment.
6. Mô hình dữ liệu: các bảng, khóa, partition, ý nghĩa cột chính.
7. Setup từ clone mới: local (ADC) và VM (service account, Secret Manager, systemd).
8. Vận hành: các lệnh, cờ, cách xem log, cách chạy lại sau lỗi, cách duyệt ứng viên kênh.
9. Lưu trữ và tuân thủ: tóm tắt từ `docs/data_retention.md`, xử lý dữ liệu cá nhân.
10. Hạn chế đã biết: collab, Shorts, comment bị sửa, độ phủ comment theo mẫu.
11. Truy vấn mẫu: top video theo tăng trưởng view 7 ngày, tỷ lệ tắt comment theo nghệ sĩ, coverage.

**Done khi**
- Người khác làm theo README trên một máy mới, chạy được `init-schema` và `run --offline` mà không cần hỏi thêm.

---

## Task 4.8 — Báo cáo Word

**Cấu trúc đề xuất**

1. Tóm tắt: mục tiêu, kết quả chính trong 5–7 dòng với số liệu thật.
2. Phạm vi và nguồn dữ liệu.
3. Kiến trúc và quyết định thiết kế (quota, transaction, snapshot, kênh phụ).
4. Kết quả: bảng coverage, bảng quota, kết quả quality checks.
5. Bằng chứng vận hành: hai lượt tự động, đối chiếu `run_id`.
6. Hạn chế, rủi ro còn lại.
7. Việc tiếp theo: thời gian dự kiến xong backlog, đề xuất xin tăng quota, bảng `video_artists`, dashboard.
8. Phụ lục: ảnh chụp, truy vấn.

**Done khi**
- Mọi con số trong báo cáo truy được về file trong `docs/evidence/`. Không dùng ước lượng thay cho số thực tế.

---

## Task 4.9 — Thu bằng chứng và đóng gói hồ sơ

**Danh sách bằng chứng**

| Bằng chứng | File |
|---|---|
| Link repo và commit hash triển khai | README + báo cáo |
| Ảnh chart và file danh mục | `docs/evidence/chart_<week>.png`, `data/artists.csv` |
| API đã bật, trang quota | ảnh D1 |
| Schema BigQuery | ảnh hoặc `bq show --schema` |
| Log test 3 và 10 nghệ sĩ | `d2_run_*.log`, `d3_10_artists.md` |
| Test ngắt giữa chừng | `d3_interrupt_test.md` |
| VM chạy tay | log D3 |
| `systemctl list-timers` | ảnh D3 |
| Lượt 23:00 và 07:00 | `run_2300_*.md`, `run_0700_*.md`, `run_reconciliation.md` |
| Quality checks | `quality_checks_<date>.csv` |
| Coverage và quota | `coverage_<date>.csv`, `quota_<date>.csv` |
| Discovery và duyệt kênh | truy vấn `channel_candidates` + quyết định |

**Các bước**

1. Kiểm tra đủ file theo bảng trên.
2. Rà secret lần cuối: `git log -p | grep -iE "AIza|private_key"` phải rỗng.
3. Commit cuối, tag `v1.0-submission`.
4. Ghi `daily_log.md` mục D4.

**Done khi**
- Hồ sơ đủ theo mục 16 của kế hoạch. Tag đã push. Commit của tag trùng commit đang chạy trên VM.

---

## Checklist cuối ngày D4

- [ ] Lượt 07:00 có log và dòng `pipeline_runs`
- [ ] Đối chiếu hai lượt theo `run_id`, tổng unit trong ngân sách
- [ ] Quality checks: không `FAIL` ở Khóa/Liên kết/Checkpoint, mọi `WARN` có giải thích
- [ ] Ứng viên kênh đã duyệt hoặc ghi backlog
- [ ] Commit cuối trên VM bằng tag nộp bài
- [ ] Bảng coverage và quota từ truy vấn thật
- [ ] README hoàn chỉnh, test được trên máy mới
- [ ] Báo cáo Word
- [ ] Đủ bằng chứng, không có secret trong repo

## Rủi ro trong ngày và cách xử lý

| Rủi ro | Xử lý |
|---|---|
| Lượt 07:00 không chạy hoặc `FAILED` | Ghi lại nguyên nhân, sửa, chạy tay trên VM để có bằng chứng thay thế; dùng lượt 23:00 D4 làm bằng chứng tự động bổ sung |
| Quality check `FAIL` ở khóa trùng | Ưu tiên số 1: tìm MERGE sai, sửa, dọn dữ liệu trùng bằng truy vấn có ghi lại, chạy lại check |
| Độ phủ comment thấp | Đây là hệ quả dự kiến của quota. Báo cáo số thật, nêu chính sách lấy mẫu và thời gian dự kiến xong |
| Thiếu thời gian viết báo cáo | README và bảng số liệu là bắt buộc; phần thảo luận trong báo cáo có thể ngắn lại |

## Sau D4

- Hệ thống tiếp tục chạy hai lượt mỗi ngày để giảm backlog.
- Theo dõi alert. Nếu cần mở rộng, xem xét xin tăng quota YouTube Data API theo quy trình audit của Google.
