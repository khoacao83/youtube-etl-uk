"""Pipeline catalogue: chuẩn hóa dữ liệu bảng xếp hạng nghệ sĩ YouTube UK."""

import csv
from datetime import datetime, timezone
from pathlib import Path
import re
import unicodedata


def slugify(text: str) -> str:
    """Tạo slug chuẩn hóa tên nghệ sĩ (bỏ dấu, ký tự đặc biệt, chuyển chữ thường, nối bằng -)."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("utf-8")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def normalize_chart(
    raw_path: str | Path,
    output_path: str | Path,
    week: str = "20261119",
    week_start: str = "2026-11-13",
    week_end: str = "2026-11-19",
    source_url: str = "https://charts.youtube.com/charts/TopArtists/gb/weekly",
) -> Path:
    """Đọc file raw YouTube Chart Top Artists, chuẩn hóa và xuất data/artists.csv.

    Args:
        raw_path: Đường dẫn file raw CSV.
        output_path: Đường dẫn file xuất artists.csv.
        week: Mã tuần (YYYYMMDD), ví dụ '20261119'.
        week_start: Ngày bắt đầu tuần (YYYY-MM-DD), ví dụ '2026-11-13'.
        week_end: Ngày kết thúc tuần (YYYY-MM-DD), ví dụ '2026-11-19'.
        source_url: URL nguồn dữ liệu.

    Returns:
        Path của file output đã tạo.
    """
    raw_path = Path(raw_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fetched_at = datetime.now(timezone.utc).isoformat()
    rows_to_write = []

    with open(raw_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rank_value = int(r["Rank"])
            artist_name = r["Artist Name"].strip()
            artist_slug = slugify(artist_name)
            artist_id = f"uk-{week}-{rank_value:03d}-{artist_slug}"

            rows_to_write.append({
                "artist_id": artist_id,
                "rank": rank_value,
                "artist_name": artist_name,
                "chart_week_start": week_start,
                "chart_week_end": week_end,
                "source_url": source_url,
                "fetched_at": fetched_at,
                "chart_artist_url": r.get("chart_artist_url", ""),
            })

    rows_to_write.sort(key=lambda x: x["rank"])
    fieldnames = [
        "artist_id",
        "rank",
        "artist_name",
        "chart_week_start",
        "chart_week_end",
        "source_url",
        "fetched_at",
        "chart_artist_url",
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_to_write)

    return output_path
