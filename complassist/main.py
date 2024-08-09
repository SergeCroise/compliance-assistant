# SPDX-FileCopyrightText: 2024 DB Systel GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""
Toolset that helps you with creating and interacting with SBOMs, enriching with
licensing and copyright information, and checking for Open Source license
compliance
"""

import argparse
import logging
import sys

from . import __version__
from ._clearlydefined import (
    get_clearlydefined_license_and_copyright,
    print_clearlydefined_result,
    purl_to_cd_coordinates,
)
from ._helpers import dict_to_json
from ._licensing import list_all_licenses
from ._sbom_enrich import enrich_sbom_with_clearlydefined
from ._sbom_generate import generate_cdx_sbom
from ._sbom_parse import extract_items_from_cdx_sbom

parser = argparse.ArgumentParser(description=__doc__)
subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

# SBOM Generator
parser_sbom_gen = subparsers.add_parser(
    "sbom-generate",
    help="Generate a CycloneDX SBOM using the cdxgen Docker image",
)
parser_sbom_gen.add_argument(
    "-d",
    "--directory",
    help="Path to the directory of the code repository that shall be analysed",
    required=True,
)
parser_sbom_gen.add_argument(
    "-o",
    "--output",
    help=(
        "Path where the generated SBOM shall be saved. "
        "If unset, it will be stored in a temporary directory."
    ),
)

# Enrich a SBOM with ClearlyDefined data
parser_sbom_enrich = subparsers.add_parser(
    "sbom-enrich",
    help="Enrich a CycloneDX SBOM and its licensing/copyright data via ClearlyDefined",
)
parser_sbom_enrich.add_argument(
    "-f",
    "--file",
    help="Path to the SBOM that shall be enriched",
    required=True,
)
parser_sbom_enrich.add_argument(
    "-o",
    "--output",
    help="Path where the enriched SBOM shall be saved",
    required=True,
)

# SBOM Parser
parser_sbom_read = subparsers.add_parser(
    "sbom-parse",
    help="Parse a CycloneDX SBOM and extract contained information",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
parser_sbom_read.add_argument(
    "-f",
    "--file",
    help="Path to the CycloneDX SBOM (JSON format) that shall be parsed",
    required=True,
)
parser_sbom_read.add_argument(
    "-e",
    "--extract",
    default="purl,licenses-short",
    help="Information that shall be retrieved from each contained component. Comma-separated list.",
)
parser_sbom_read.add_argument(
    "-o",
    "--output",
    default="json",
    choices=["json", "dict", "none"],
    help="Desired output format.",
)
parser_sbom_read.add_argument(
    "--no-simplify",
    help="Do not simplify SPDX license expression using flict. May increase speed",
    action="store_true",
)

# ClearlyDefined
parser_cd = subparsers.add_parser(
    "clearlydefined",
    help="Gather license information from ClearlyDefined for a package",
)
parser_cd_exclusive = parser_cd.add_mutually_exclusive_group(required=True)
parser_cd_exclusive.add_argument(
    "-p",
    "--purl",
    help=(
        "The purl for which ClearlyDefined licensing information is searched. "
        "If -c is used, this is preferred."
    ),
)
parser_cd_exclusive.add_argument(
    "-c",
    "--coordinates",
    help=(
        "The ClearlyDefined coordinates for which ClearlyDefined licensing information is searched"
    ),
)
parser_cd_exclusive.add_argument(
    "--purl-to-coordinates",
    help=(
        "Convert a Package URL (purl) to ClearlyDefined coordinates, and show result. "
        "Cannot be combined with -p and -c."
    ),
)

# License Compliance
parser_licensing = subparsers.add_parser(
    "licensing",
    help="Help with checking and reaching Open Source license compliance",
)
licensing_subparser = parser_licensing.add_subparsers(
    dest="licensing_command",
    help="Available licensing commands",
)

# List licenses
licensing_list = licensing_subparser.add_parser(
    "list",
    help="List all detected licenses",
)
licensing_list.add_argument(
    "-f",
    "--file",
    help="Path to the CycloneDX SBOM (JSON format) from which licenses are read",
    required=True,
)
licensing_list.add_argument(
    "-o",
    "--output",
    default="json",
    choices=["json", "dict", "plain", "none"],
    help="Desired output format.",
)
licensing_list.add_argument(
    "--no-simplify",
    help="Do not simplify SPDX license expression using flict. May increase speed",
    action="store_true",
)


# General flags
parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
parser.add_argument("--version", action="version", version="%(prog)s " + __version__)


def configure_logger(args) -> logging.Logger:
    """Set logging options"""
    log = logging.getLogger()
    logging.basicConfig(
        encoding="utf-8",
        format="%(levelname)s: %(message)s",
        level=(logging.DEBUG if args.verbose else logging.INFO),
    )

    return log


def main():  # pylint: disable=too-many-branches
    """Main function"""

    args = parser.parse_args()

    # Set logger
    configure_logger(args=args)

    # Debug arguments
    logging.debug(args)

    # Generate SBOM with cdxgen
    if args.command == "sbom-generate":
        generate_cdx_sbom(args.directory, args.output)

    # Enrich SBOM by ClearlyDefined data
    elif args.command == "sbom-enrich":
        enrich_sbom_with_clearlydefined(args.file, args.output)

    # Parse info from SBOM
    elif args.command == "sbom-parse":
        # Convert comma-separated information to list
        info = args.extract.split(",")
        extraction = extract_items_from_cdx_sbom(
            args.file, information=info, use_flict=not args.no_simplify
        )
        if args.output == "json":
            print(dict_to_json(extraction))
        elif args.output == "dict":
            print(extraction)
        elif args.output == "none":
            pass

    # Get ClearlyDefined license/copyright data for a package
    elif args.command == "clearlydefined":
        if args.purl_to_coordinates:
            print(purl_to_cd_coordinates(args.purl_to_coordinates))

        elif args.coordinates or args.purl:
            if args.purl:
                coordinates = purl_to_cd_coordinates(args.purl)
            else:
                coordinates = args.coordinates

            print_clearlydefined_result(get_clearlydefined_license_and_copyright(coordinates))

    # License compliance commands
    elif args.command == "licensing":
        # List all detected licenses in an SBOM, unified and sorted
        if args.licensing_command == "list":
            all_licenses = list_all_licenses(sbom_path=args.file, use_flict=not args.no_simplify)
            if args.output == "json":
                print(dict_to_json(all_licenses))
            elif args.output == "dict":
                print(all_licenses)
            elif args.output == "plain":
                print("\n".join(all_licenses))
            elif args.output == "none":
                pass

        # No subcommand given, show help
        else:
            parser_licensing.print_help()

    else:
        logging.critical("No valid command provided!")
        sys.exit(1)


if __name__ == "__main__":
    main()
