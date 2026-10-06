"""Materialize source-reviewed supply-chain manufacturing regions."""

from __future__ import annotations

import argparse
import json

from app.db.session import get_session_factory
from app.supply_chain_sites import materialize_supply_chain_sites


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-supply-chain-sites")
    parser.add_argument("--ticker")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    with get_session_factory()() as session:
        result = materialize_supply_chain_sites(session, ticker=args.ticker)
        session.commit()
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
