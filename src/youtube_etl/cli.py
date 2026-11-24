import argparse
def main():
    parser = argparse.ArgumentParser(
        prog="youtube_etl",
        description="Youtube ETL Top 100 UK Data Pipeline",
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        default="dev",
        help="Environment to run the ETL pipeline (default: dev)",
    )
    args = parser.parse_args()

if __name__ == "__main__":
    main()