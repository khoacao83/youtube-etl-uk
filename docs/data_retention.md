1. Các chính sách cốt lỏi của Youtube

# Thời hạn tối đa được giữ dữ liệu không làm mới là bao lâu?
  • Chính sách (Section III.E.1 - Storage and Caching):
  Google quy định không được lưu trữ API data quá 30 ngày (30 calendar days) mà không làm mới (refresh) từ API.
  • Quyết định: Mọi dữ liệu metadata của Video, Kênh và Comment lưu trong database phải được làm mới định kỳ tối đa 30 ngày một lần (REFRESH_AFTER_DAYS = 30). Nếu sau 30 ngày không thể làm mới (hoặc không còn theo dõi), dữ liệu đó phải
  bị xóa hoặc vô hiệu hóa.

# video_stats_history được giữ bao âu? Có cần cơ chế riêng không?
 • Chính sách (Section III.E.2 - Metrics & Historical Data):
  Google cho phép lưu trữ số liệu thống kê lịch sử (views, likes, comments count) cho mục đích báo cáo và phân tích xu hướng (analytical/historical trending), miễn là số liệu này được gắn với mốc thời gian cụ thể (snapshot date) và
  không bị trình bày như số liệu thời gian thực.                                                                                                                                                                                           
  • Quyết định: Bảng clean.video_stats_history được phép lưu giữ lâu dài (ví dụ: 365 ngày hoặc không giới hạn) phục vụ bài toán vẽ biểu đồ tăng trưởng theo thời gian. Cơ chế riêng: Mỗi ngày chỉ ghi 1 bản ghi snapshot (partition theo
  snapshot_date), không sửa đổi dữ liệu quá khứ.     

# Comment và thông tin tác giả cần làm mới hay xóa khi nào?
Người dùng trên YouTube có quyền sửa, xóa bình luận hoặc xóa tài khoản bất cứ lúc nào. Ứng dụng phải tôn trọng điều này.
    • Quyết định:
      • Comment chỉ lưu tối đa 30 ngày (COMMENT_RETENTION_DAYS = 30).
      • Khi pipeline chạy đợt làm mới, nếu comment không còn tồn tại trên YouTube (người dùng đã xóa), pipeline phải xóa bản ghi đó trong clean.comments.
      • Bảo vệ danh tính tác giả: Không lưu ảnh đại diện (avatar URL), không lưu tên hiển thị nhạy cảm. Cột author_channel_id phải được băm bằng thuật toán SHA-256 kèm chuỗi Salt bí mật (hash(salt + channel_id)) để phân tích hành vi mà
      không để lộ danh tính người dùng.

# Khi video hoặc kênh bị gỡ thì phải xử lý thế nào?
    • Chính sách: Khi một video/kênh bị chủ sở hữu xóa hoặc chuyển sang chế độ riêng tư (Private/Deleted), API sẽ trả về lỗi 404 Not Found hoặc trạng thái hạn chế.
    • Quyết định:
      • Cập nhật cờ trạng thái status = 'DELETED' hoặc is_available = FALSE.
      • Xóa các bình luận liên quan thuộc video đó để tránh lưu trữ nội dung đã bị gỡ.



2. Bảng chốt thời hạn lưu trữ cho từng bảng (Mục 7 của Kế hoạch)
  
  Để đạt tiêu chí Done khi, bảng đối chiếu thời hạn lưu trữ sẽ như sau:
  
   Bảng BigQuery                            │ Thời hạn lưu trữ                         │ Cơ chế xử lý                                       │ Lý do theo chính sách
  ──────────────────────────────────────────┼──────────────────────────────────────────┼────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────
   clean.artists                            │ Không giới hạn                           │ Cập nhật theo tuần chart                           │ Dữ liệu bảng xếp hạng công khai (YouTube Charts UK), không phải dữ liệu động từ API Data v3.
   clean.artist_channels                    │ Không giới hạn                           │ Cập nhật khi đổi kênh                              │ Danh mục mapping nghệ sĩ - kênh YouTube chính thức.
   clean.videos                             │ 30 ngày (hoặc làm mới mỗi 30 ngày)       │ Cập nhật / MERGE đè                                │ Tuân thủ Section III.E.1 (không lưu API data cũ quá 30 ngày).
   clean.comments                           │ 30 ngày                                  │ Xóa sau 30 ngày hoặc khi gốc bị xóa                │ Tuân thủ bảo vệ quyền riêng tư người dùng và quyền xóa nội dung.
   clean.video_stats_history                │ 365 ngày (hoặc không giới hạn)           │ Partition theo ngày UTC                            │ Tuân thủ ngoại lệ Section III.E.2 cho dữ liệu phân tích chuỗi thời gian (metrics trending).
   raw.api_responses                        │ 30 ngày                                  │ Tự động xóa (Table Partition Expiration = 30 days) │ Chỉ lưu raw payload phục vụ audit và debug.
   raw.staging_*                            │ 1 ngày                                   │ Truncate sau mỗi run MERGE                         │ Dữ liệu trung chuyển tạm thời.
   raw.pipeline_checkpoints                 │ Không giới hạn                           │ Ghi đè trạng thái mới nhất                         │ Dữ liệu trạng thái vận hành của pipeline, không chứa nội dung YouTube.
   raw.pipeline_runs                        │ 180 ngày                                 │ Lưu log vận hành                                   │ Dữ liệu giám sát hệ thống (logs/audit).
