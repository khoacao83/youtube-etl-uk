import csv
from pathlib import Path
import re
import unicodedata
import warnings
import pytest

def clean_name(name : str) ->str:
    text = unicodedata.normalize("NKFD",name)
    text = text.encode("acsii","ignore").decode("utf-8")
    return re.sub(r"\W+","",text).lower()

@pytest.fixture(scope="module")
def artist_data():
    csv_path= Path("data/artist_data.csv")
    assert csv_path.exists(), f"File {csv_path} does not exist"

    with open(csv_path,"r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = list(reader)
    return row

def test_row_count(artist_data):
    assert len(artist_data) == 100,(f"Yêu cầu đúng 100 dòng nhưng tìm thấy  {len(artist_data)} dòng")

def test_rank_1_to_100(artist_data):
    ranks = [int(row["Rank"]) for row in artist_data]
    assert len(ranks) == 100, f"Yêu cầu đúng 100 dòng nhưng tìm thấy {len(ranks)} dòng"
    assert set(ranks) == set(range(1,101)), f"Rank phải từ 1 đến 100 nhưng tìm thấy {set(ranks)}"

def test_artist_id_unique(artist_data):
    artist_ids = [row["artist_id"] for row in artist_data]
    assert len(artist_ids) == len(set(artist_ids)), "artist_id phải là duy nhất"
    
    pattern = re.compile(r"^uk-\d{8}-\d{3}-[a-z0-9]+$")
    for ads in artist_ids:
        assert pattern.match(ads), f"artist_id {ads} không đúng định dạng"

def test_warn_on_duplicate_artist_name(artist_data):
    seen={}
    duplicates=[]
    for row in artist_data:
        row_name = row["artist_name"]
        norm_name = clean_name(row_name)
        if norm_name in seen: 
            duplicates.append(row_name)
        else:
            seen[norm_name] = row_name
    if duplicates:
        warnings.warn(f"Có {len(duplicates)} cặp trên nghệ sĩ trùng nhau sau khi chuẩn hóa", stacklevel=2)