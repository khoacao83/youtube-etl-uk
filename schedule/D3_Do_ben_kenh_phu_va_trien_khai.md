# Day 3 — Độ bền, kênh phụ và triển khai

> Thuộc kế hoạch `Big_Project_YouTube_ETL_Top_100_UK_v2.md`. File này mô tả chi tiết việc cần làm trong ngày 3, kèm input, output và tiêu chí hoàn thành của từng việc.

## Tổng quan ngày

| Mục | Nội dung |
|---|---|
| Mục tiêu | Hệ thống chịu được gián đoạn và cạn quota; có kênh phụ `search.list`; chạy được 10 nghệ sĩ; triển khai lên VM; lượt 23:00 tự động chạy |
| Input đầu ngày | Bàn giao D2: ba pipeline chạy được, schema đầy đủ, số unit thật của 3 nghệ sĩ, danh sách `NEEDS_DISCOVERY` |
| Outcome cuối ngày | Test ngắt giữa chừng pass; discovery xử lý được nghệ sĩ cần tìm; số unit thật của 10 nghệ sĩ; VM chạy tay thành công; timer bật trước 21:00; lượt 23:00 có log và dòng trong `pipeline_runs` |
| Quota dự kiến | 2.000–4.000 unit trong giờ làm việc, cộng tối đa 45% cho lượt 23:00 |
| Thời lượng | ~10 giờ (kết thúc sau lượt 23:00) |

> **Lưu ý ngày quota:** quota reset khoảng 15:00 giờ Việt Nam. Phần test buổi sáng dùng quota của ngày cũ. Từ 15:00 trở đi, mọi test tính vào ngày quota mới, chung với lượt 23:00 và 07:00 sáng D4. Nên dồn test nặng vào buổi sáng.

## Lịch gợi ý

| Khung giờ | Việc |
|---|---|
| 08:30–10:00 | 3.1 Checkpoint, run lock, dừng mềm, trạng thái run |
| 10:00–10:45 | 3.2 Round-robin và thứ tự ưu tiên |
| 10:45–11:30 | 3.3 Test ngắt giữa chừng |
| 11:30–12:30 | 3.4 Test 10 nghệ sĩ và đo quota (trước 15:00) |
| 13:30–14:15 | 3.5 Comment tầng B |
| 14:15–15:30 | 3.6 Kênh phụ discovery (`search.list`) |
| 15:30–16:15 | 3.7 Refresh |
| 16:15–16:45 | 3.8 Test offline và CI |
| 16:45–18:30 | 3.9 Tạo VM, cài đặt, chạy tay |
| 18:30–20:30 | 3.10 systemd timer và cảnh báo (xong trước 21:00) |
| 23:00–23:30 | 3.11 Theo dõi lượt 23:00 |

---

## Task 3.1 — Checkpoint, run lock, dừng mềm

**Các bước**

1. `checkpoint.py`: `get(task_type, entity_id)` và `build_merge(task_type, entity_id, fields)` sinh câu MERGE để gộp vào transaction của batch. Không có hàm nào tự ghi checkpoint ngoài transaction.
2. Run lock: `fcntl.flock` trên `/var/lock/youtube-etl.lock` (local: `/tmp/youtube-etl.lock`). Không lấy được lock thì thoát với mã 75 và log `LOCKED`.
3. Dừng mềm: runner nhận `--deadline` (mặc định là thời điểm khởi động + 5 giờ 45 phút). Trước mỗi batch, nếu còn dưới 15 phút thì dừng nhận việc mới, commit batch hiện tại rồi kết thúc `DEFERRED`.
4. Bắt `SIGTERM`: đánh dấu dừng, hoàn tất batch đang chạy và ghi `DEFERRED`.
5. Trạng thái cuối cùng của run: `SUCCESS` (hết việc đến hạn), `DEFERRED` (còn việc do quota hoặc thời gian), `FAILED` (lỗi không phân loại được).

**Done khi**
- Hai tiến trình chạy cùng lúc: tiến trình thứ hai thoát `LOCKED`.
- `kill -TERM` giữa run cho trạng thái `DEFERRED`, không phải `FAILED`.

---

## Task 3.2 — Thứ tự ưu tiên và round-robin

**Các bước**

1. Runner chạy task theo thứ tự ở mục 4.3 của kế hoạch: stats → video mới → discovery → comment A → backlog → comment B → refresh.
2. Ngân sách con theo task, tính từ `run_cap`:

| Task | Ngân sách |
|---|---|
| stats | Tối đa cần thiết (không giới hạn trong `run_cap`) |
| videos_new | 15% |
| discovery | ≤ `SEARCH_DAILY_UNIT_CAP` còn lại trong ngày quota |
| comments_a | 35% |
| videos_backlog | 20% |
| comments_b | 20% |
| refresh | 10% |

   Phần task trước không dùng hết được dồn cho task sau.
3. Round-robin: mỗi task lặp qua nghệ sĩ bắt đầu từ `artist_id` sau nghệ sĩ cuối cùng của run trước (lưu trong checkpoint `runner_cursor`). Mỗi nghệ sĩ chỉ nhận một lát ngân sách mỗi vòng.
4. `backlog` trong `pipeline_runs`: số kênh chưa xong backlog, số video chưa lấy comment tầng A/B, số nghệ sĩ `NEEDS_DISCOVERY`.

**Done khi**
- Test unit: với ngân sách nhỏ, 10 nghệ sĩ đều nhận ít nhất một lát trước khi nghệ sĩ nào nhận lát thứ hai.

---

## Task 3.3 — Test ngắt giữa chừng

**Các bước**

1. Ghi lại số dòng và checkpoint của 3 nghệ sĩ D2.
2. Chạy backlog video cho một nghệ sĩ nhiều video, rồi `kill -9` khi log báo đang ở batch thứ 2–3.
3. Kiểm tra:
   - Dữ liệu các batch đã commit còn nguyên.
   - Checkpoint trỏ đúng batch cuối đã commit, không vượt qua.
   - Run bị kill vẫn ở `RUNNING` trong `pipeline_runs`. Run kế tiếp phải phát hiện run mồ côi (`RUNNING` quá `TimeoutStartSec`) và chuyển nó sang `FAILED` với lý do `ORPHANED`.
4. Chạy lại: tiếp tục đúng vị trí, không trùng dòng.
5. Lặp lại thử nghiệm với pipeline comment.

**Output:** `docs/evidence/d3_interrupt_test.md` gồm lệnh, log và truy vấn trước/sau.

**Done khi**
- Không mất dòng đã commit, không trùng dòng, checkpoint không vượt dữ liệu.

---

## Task 3.4 — Test 10 nghệ sĩ và đo quota

**Chọn nghệ sĩ:** trải đều theo rank (ví dụ hạng 1, 10, 20, …, 90), gồm cả nghệ sĩ có kênh VEVO.

**Các bước**

1. `python -m youtube_etl run --env dev --max-artists 10 --max-units 2500`.
2. Ghi lại:
   - Unit theo endpoint và theo task.
   - Thời gian chạy và thời gian trung bình mỗi request.
   - Tổng video của 10 kênh, tỷ lệ video tắt comment.
   - Số trang comment trung bình mỗi video tầng A.
3. Ngoại suy cho 100 nghệ sĩ và cập nhật bảng mục 4.5 của kế hoạch: `V` thật, unit stats mỗi ngày, số ngày ước tính để xong backlog video.
4. Nếu stats hằng ngày cộng video mới vượt 30% ngày quota, giảm phạm vi (ví dụ chỉ lấy stats cho video loại `REGULAR`, hoặc chỉ video trong N năm gần nhất) và ghi quyết định này.

**Output:** `docs/evidence/d3_10_artists.md` và bảng quota đã cập nhật.

**Done khi**
- Có số liệu thật và quyết định phạm vi rõ ràng trước khi triển khai VM.

---

## Task 3.5 — Comment tầng B

**Các bước**

1. Với mỗi nghệ sĩ, chọn top 5 video theo `view_count` trong snapshot gần nhất, loại các video đã thuộc tầng A.
2. Gọi `commentThreads.list` với `order=relevance`, tối đa 3 trang, cùng xử lý reply như tầng A.
3. Ghi `sample_mode = RELEVANCE_SAMPLE` và checkpoint `comments_b.sample_done = true`.
4. Comment đã có từ tầng A thì giữ `sample_mode` cũ (MERGE không ghi đè cột này).

**Done khi**
- Mỗi nghệ sĩ trong test 10 có tối đa 5 video tầng B được xử lý hoặc ghi `DEFERRED_QUOTA`.

---

## Task 3.6 — Kênh phụ discovery (`search.list`)

**Input:** danh sách nghệ sĩ `NEEDS_DISCOVERY` từ D2; mục 3.3 của kế hoạch.

**Các bước**

1. `pipelines/discovery.py`:
   - **Điều kiện chạy:** `SEARCH_FALLBACK_ENABLED = true`, có nghệ sĩ thỏa điều kiện (`NEEDS_DISCOVERY`, kênh mới chuyển `UNAVAILABLE`, hoặc gọi tay), còn ngân sách search trong ngày quota, và nghệ sĩ không trong thời gian cooldown.
   - Không có việc → log `SKIPPED_NOT_NEEDED`, 0 unit.
2. Cho mỗi nghệ sĩ (tối đa `SEARCH_MAX_CALLS_PER_ARTIST` lệnh):
   - Lệnh 1: `search.list(part=snippet, type=channel, q="<artist_name>", maxResults=10)`.
   - Lệnh 2 (chỉ khi lệnh 1 không có ứng viên đạt ngưỡng): biến thể tên (bỏ dấu, thêm "official" hoặc "VEVO").
   - Gom `channel_id`, gọi `channels.list` theo batch (1 unit).
3. Chấm điểm 0–100:

| Tiêu chí | Điểm |
|---|---|
| Tên kênh khớp tên nghệ sĩ sau chuẩn hóa | 40 |
| Handle hoặc customUrl chứa tên | 15 |
| Subscriber thuộc nhóm cao nhất trong ứng viên | 20 |
| Mô tả nhắc tên nghệ sĩ | 10 |
| Có uploads và số video > 0 | 10 |
| Tên kênh không chứa "- Topic", "fan", "lyrics" | 5 |

4. Ghi mọi ứng viên vào `raw.channel_candidates` (`score`, `score_reasons`, `status = PENDING_REVIEW`, `discovered_run_id`). Cập nhật checkpoint `discovery` (`last_search_at`, `calls_used`).
5. **Không** ghi trực tiếp vào `clean.artist_channels`.
6. Lệnh duyệt: `python -m youtube_etl review-candidates --artist-id X --accept <channel_id>` cập nhật `artist_channels.csv` với `verification_method = T3_SEARCH_REVIEWED` và `evidence_url` bắt buộc.
7. Test:
   - Unit test với fixture: không chạy khi tắt cờ, không chạy khi hết ngân sách, tôn trọng cooldown, không vượt số lệnh mỗi nghệ sĩ.
   - Chạy thật cho 1–2 nghệ sĩ `NEEDS_DISCOVERY`. Nếu không có nghệ sĩ nào cần, chạy `--task discovery --artist-id <id>` thủ công cho một nghệ sĩ đã `VERIFIED` để kiểm chứng điểm số. Ghi `trigger=manual_validation` và không ghi đè kênh đã xác minh.

**Output:** discovery hoạt động; ứng viên trong `raw.channel_candidates`.

**Done khi**
- Unit search trong `pipeline_runs` ≤ `SEARCH_DAILY_UNIT_CAP`.
- Run bình thường không có nghệ sĩ cần tìm tốn 0 unit search.
- Không ứng viên nào tự trở thành `VERIFIED`.

---

## Task 3.7 — Refresh

**Các bước**

1. Chọn video có `last_checked_at` cũ hơn `REFRESH_AFTER_DAYS` (theo quyết định D1), giới hạn bởi ngân sách task.
2. Gọi `videos.list(part=id,status)`. ID không trả về thì `is_available = false` và ghi `removed_at`.
3. Gọi `channels.list` cho kênh `VERIFIED` mỗi ngày một lần (100 kênh ≈ 2 unit). Kênh không trả về thì `UNAVAILABLE` và nghệ sĩ chuyển `NEEDS_DISCOVERY`.
4. Xóa theo chính sách: lệnh `python -m youtube_etl purge` xóa comment và stats của video có `removed_at` quá thời hạn đã chốt.

**Done khi**
- Test với một `video_id` giả không tồn tại: video bị đánh dấu đúng.

---

## Task 3.8 — Test offline và CI

**Các bước**

1. Ghi response thật thành fixture trong `tests/fixtures/` (đã làm sạch: bỏ API key, hash tác giả).
2. Cờ `--offline` cho client đọc fixture thay vì gọi API.
3. Test chính: phân trang, dừng ở watermark, comment tắt, quota cạn giữa batch, transaction rollback (mock), discovery bị chặn.
4. CI chạy toàn bộ test offline.

**Done khi**
- CI xanh. `pytest -m "not integration"` không gọi mạng.

---

## Task 3.9 — Tạo VM, cài đặt, chạy tay

**Các bước**

1. Tạo VM:
   ```bash
   gcloud compute instances create yt-etl-vm \
     --zone=asia-southeast1-b --machine-type=e2-small \
     --image-family=debian-12 --image-project=debian-cloud \
     --service-account=yt-etl-runner@<project>.iam.gserviceaccount.com \
     --scopes=cloud-platform --no-address
   ```
   Lệnh này không gán IP công khai, nên cần Cloud NAT để VM gọi được API. Nếu muốn giới hạn API key theo IP, dùng IP tĩnh của Cloud NAT.
2. SSH qua IAP: `gcloud compute ssh yt-etl-vm --tunnel-through-iap`.
3. Cài đặt:
   ```bash
   sudo apt-get update && sudo apt-get install -y python3-venv git
   sudo useradd -r -m -d /opt/youtube-etl-uk etl
   sudo -u etl git clone <repo> /opt/youtube-etl-uk && cd /opt/youtube-etl-uk
   sudo -u etl git checkout <commit đã test>
   sudo -u etl python3 -m venv .venv && sudo -u etl .venv/bin/pip install -e .
   ```
4. Tạo `/etc/youtube-etl/env` (quyền `600`, chủ `etl`) từ `.env.example`, đặt `ENV=prod` hoặc dev theo quyết định môi trường.
5. Nếu dùng prod thì tạo dataset `yt_uk_prod_*`, cấp quyền và chạy `init-schema` + `load-catalogue`.
6. Chạy tay trên VM: `sudo -u etl .venv/bin/python -m youtube_etl run --max-artists 3 --max-units 300`.

**Output:** VM chạy được, log chạy tay.

**Done khi**
- `pipeline_runs` có dòng `trigger=manual` từ VM với `git_commit` đúng.
- Không có file key nào trên đĩa: VM lấy key từ Secret Manager qua service account.

---

## Task 3.10 — systemd timer và cảnh báo (xong trước 21:00)

**Các bước**

1. Kiểm tra `systemd --version` (Debian 12 là 252, hỗ trợ timezone trong `OnCalendar`).
2. Cài `deploy/systemd/youtube-etl.service` và `youtube-etl.timer` theo mục 9.1 của kế hoạch vào `/etc/systemd/system/`.
3. Kích hoạt:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now youtube-etl.timer
   systemctl list-timers youtube-etl.timer
   ```
   Kết quả phải hiển thị lần chạy kế tiếp lúc 23:00 giờ Việt Nam.
4. Chạy thử service một lần với giới hạn nhỏ: `sudo systemctl start youtube-etl.service` (tạm thêm `--max-units 100` qua biến môi trường), rồi `journalctl -u youtube-etl.service -n 100`. Sau đó gỡ giới hạn.
5. Cài Ops Agent hoặc đảm bảo journald đẩy log lên Cloud Logging.
6. Tạo log-based alert: log có `status="FAILED"` từ runner → gửi email.

**Output:** ảnh `systemctl list-timers`, `journalctl` của lần thử, cấu hình alert.

**Done khi**
- Timer hiển thị next trigger 23:00 ICT. Lần thử service kết thúc `SUCCESS` hoặc `DEFERRED`.

---

## Task 3.11 — Theo dõi lượt 23:00

**Các bước**

1. Từ 23:00, theo dõi `journalctl -u youtube-etl.service -f`.
2. Sau khi xong, kiểm tra:
   ```sql
   SELECT run_id, trigger, status, started_at, ended_at, units_total, units_by_endpoint, backlog
   FROM raw.pipeline_runs ORDER BY started_at DESC LIMIT 3;
   ```
3. Xác nhận `units_total` ≤ 45% quota và `snapshot_date` là ngày UTC đúng.
4. Lưu log và kết quả truy vấn vào `docs/evidence/run_2300_<date>.md`.

**Done khi**
- Có một run `trigger=timer` lúc 23:00 kết thúc `SUCCESS` hoặc `DEFERRED`.

---

## Checklist cuối ngày D3

- [ ] Run lock, dừng mềm, xử lý `SIGTERM`, phát hiện run mồ côi
- [ ] Thứ tự ưu tiên và round-robin có test
- [ ] Test ngắt giữa chừng có bằng chứng
- [ ] Số liệu quota thật của 10 nghệ sĩ, bảng 4.5 đã cập nhật
- [ ] Comment tầng B
- [ ] Discovery: tôn trọng cờ, trần, cooldown; có ứng viên chờ duyệt; 0 unit khi không cần
- [ ] Refresh và lệnh purge
- [ ] Test offline, CI xanh
- [ ] VM chạy tay thành công, không có key trên đĩa
- [ ] Timer bật trước 21:00, alert đã cấu hình
- [ ] Lượt 23:00 có log và dòng `pipeline_runs`

## Rủi ro trong ngày và cách xử lý

| Rủi ro | Xử lý |
|---|---|
| Test buổi chiều ăn vào quota của lượt 23:00 | Dồn test nặng trước 15:00; buổi chiều dùng `--offline` hoặc `--max-units` nhỏ |
| VM không ra được Internet | Kiểm tra Cloud NAT; tạm gán IP ephemeral để không lỡ lượt 23:00 |
| Timer không chạy đúng giờ | Kiểm tra `timedatectl`, `systemctl list-timers`; nếu timezone trong `OnCalendar` không hỗ trợ, đặt timezone VM là `Asia/Ho_Chi_Minh` |
| Lượt 23:00 `FAILED` | Không sửa nóng trên VM. Ghi lỗi, sửa trên local với dev, triển khai commit mới trước 07:00 nếu kịp |
| Không có nghệ sĩ `NEEDS_DISCOVERY` để test thật | Dùng chế độ `manual_validation` như mô tả ở 3.6 |

## Bàn giao sang D4

- Input cho D4: commit đang chạy trên VM; `run_id` của lượt 23:00; số liệu 10 nghệ sĩ; danh sách ứng viên chờ duyệt; danh sách lỗi còn mở.
