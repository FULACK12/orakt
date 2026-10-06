"""Command-line import of reusable local geography reference data."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.db.session import get_session_factory
from app.geography.geonames import import_geonames
from app.geography.regional_population import (
    import_china_census_population,
    import_statcan_population,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-geography")
    subparsers = parser.add_subparsers(dest="command", required=True)
    import_parser = subparsers.add_parser(
        "import-geonames",
        help="Import admin1CodesASCII.txt and a GeoNames cities ZIP",
    )
    import_parser.add_argument("--admin1", type=Path, required=True)
    import_parser.add_argument("--cities", type=Path, required=True)
    import_parser.add_argument(
        "--countries",
        nargs="*",
        help="Optional two-letter country codes; omit to import all countries",
    )
    statcan_parser = subparsers.add_parser(
        "import-statcan-population",
        help="Import the latest provincial population from table 17-10-0005-01",
    )
    statcan_parser.add_argument("--archive", type=Path, required=True)
    subparsers.add_parser(
        "import-china-census-population",
        help="Import official 2020 permanent-resident population for 31 provinces",
    )
    return parser


def main() -> None:
    """Validate arguments and run the requested geography import."""
    args = build_parser().parse_args()
    if args.command == "import-statcan-population":
        with get_session_factory()() as session:
            statcan_result = import_statcan_population(
                session,
                archive_path=args.archive,
            )
            session.commit()
        print(statcan_result.model_dump_json(indent=2))
        return
    if args.command == "import-china-census-population":
        with get_session_factory()() as session:
            china_result = import_china_census_population(session)
            session.commit()
        print(china_result.model_dump_json(indent=2))
        return
    countries = set(args.countries) if args.countries else None
    with get_session_factory()() as session:
        geonames_result = import_geonames(
            session,
            admin1_path=args.admin1,
            cities_zip_path=args.cities,
            countries=countries,
        )
        session.commit()
    print(geonames_result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
