create table if not exists '${CLEAN}.artists' (
    artist_id string not null,
    rank int64 not null,
    artist_name string not null,
    chart_week_start date not null,
    chart_week_end date not null,
    source_url string,
    chart_artist_url string,
    run_id string not null,
    fetched_at timestamp not null,
    load_timestamp timestamp not null,
    primary key (artist_id, chart_week_start) not enforced
)
cluster by artist_id;

CREATE TABLE IF NOT EXISTS '${CLEAN}.artist_channels' (
    artist_id string not null,
    channel_id string not null,
    channel_title string,
    chanle_role string,
    status string,
    verification_method string,
    evidence_url string,
    uploads_playlist_id string,
    video_count int64,
    subcriber_count int64,
    verified_at timestamp,
    run_id string not null,
    fetch_at timestamp not null,
    load_timestamp timestamp not null
    primary key(artist_id, channel_id) not enforced
)
cluster by artist_id, channel_id;

CREATE TABLE IF NOT EXISTS '${RAW}.staging_artists' (
    artist_id string not null,
    rank int64 not null,
    artist_name string not null,
    chart_week_start date not null,
    chart_week_end date not null,
    source_url string,
    chart_artist_url string,
    run_id string not null,
    batch_id string,
    fetched_at timestamp not null,
    load_timestamp timestamp not null
)
partition by date(load_timestamp)
cluster by run_id
options (partition_expiration_days = 7);

create table if not exists '${RAW}.staging_artist_channels'(
    artist_id string not null,
    channel_id string not null,
    channel_title string,
    channel_role string,
    status string not null,
    verification_method string,
    evidence_url string,
    uploads_playlist_id string,
    video_count int64,
    subcriber_count int64,
    verified_at timestamp,
    run_id string not null,
    fetched_at timestamp not null,
    load_timestamp timestamp not null
)
partition by date(load_timestamp)
cluster by run_id
options (partition_exporation_days = 7 );