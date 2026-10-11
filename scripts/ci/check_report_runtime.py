"""Check that the report image has its tools but no Marimo runtime."""

import importlib.util
import shutil
from importlib.metadata import PackageNotFoundError, version


def main():
    for tool in ("snakemake", "pytest", "quarto", "Rscript"):
        if shutil.which(tool) is None:
            raise SystemExit(f"FAIL: required executable missing: {tool}")

    if importlib.util.find_spec("marimo") is not None:
        raise SystemExit("FAIL: Marimo module is importable.")

    if shutil.which("marimo") is not None:
        raise SystemExit("FAIL: Marimo executable is present.")

    try:
        version("marimo")
    except PackageNotFoundError:
        pass
    else:
        raise SystemExit("FAIL: Marimo distribution is installed.")

    print("PASS: report tools are present and Marimo is absent.")


if __name__ == "__main__":
    main()
