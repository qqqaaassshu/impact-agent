import argparse

from impact_agent import __version__


def main() -> None:
    parser = argparse.ArgumentParser(prog="impact-agent")
    parser.add_argument("--version", action="store_true", help="Show version and exit.")
    args = parser.parse_args()

    if args.version:
        print(__version__)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
