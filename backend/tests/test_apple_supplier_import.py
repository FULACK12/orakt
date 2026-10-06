"""Apple supplier-list layout parser tests."""

from app.apple_supplier_import import parse_supplier_layout_page


def test_supplier_layout_parser_retains_supplier_and_continuation_locations() -> None:
    supplier_start = 30
    location_start = 120
    header = (
        " " * supplier_start
        + "SUPPLIER NAME"
        + " " * (location_start - supplier_start - len("SUPPLIER NAME"))
        + "PRIMARY LOCATIONS WHERE MANUFACTURING FOR APPLE OCCURS"
    )

    def row(name: str, location: str) -> str:
        return " " * supplier_start + name.ljust(location_start - supplier_start) + location

    layout = "\n".join(
        (
            header,
            row("Micron Technology Incorporated", "Shaanxi    China mainland"),
            row("", "Hiroshima    Japan"),
            row("", "Singapore    Singapore"),
            row(
                "Taiwan Semiconductor Manufacturing Company Limited",
                "Shanghai    China mainland",
            ),
            row("", "Taiwan    Taiwan"),
        )
    )

    rows = parse_supplier_layout_page(layout)

    assert [row.name for row in rows] == [
        "Micron Technology Incorporated",
        "Taiwan Semiconductor Manufacturing Company Limited",
    ]
    assert "Hiroshima" in rows[0].manufacturing_locations
    assert "Taiwan" in rows[1].manufacturing_locations
