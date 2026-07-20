"""Pipeline scheduler — runs all pipeline steps on a daily schedule.

This module discovers and imports every Python file in the `pipeline/`
directory (sorted alphabetically), then executes them in order twice daily.
Used in production to keep predictions up-to-date.
"""

from __future__ import annotations

import datetime as dt
import glob
import importlib
import os
import sys
import time

import schedule

# Ensure the pipeline package is importable
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "pipeline"))


def _import_module(pipeline: str, step: str):
    """Import a single pipeline step module."""
    return importlib.import_module(f"{pipeline}.{step}")


def _discover_pipeline(pipeline_dir: str = "pipeline"):
    """Return a sorted list of pipeline step modules (excluding util.py)."""
    flist = sorted(
        f for f in glob.iglob(f"{pipeline_dir}/*.py")
        if not f.endswith("util.py")
    )
    return [_import_module(*f[:-3].split("/")) for f in flist]


def run_pipeline(steps):
    """Execute every step in sequence. Logs success/failure."""
    print(f"Pipeline run started at {dt.datetime.now()}")
    try:
        for step in steps:
            step.run()
    except Exception as e:
        print(f"Pipeline failed in {step.__name__} at {dt.datetime.now()}: {e}")
    else:
        print(f"Pipeline completed successfully at {dt.datetime.now()}")


def main():
    os.environ["CONFIG_DIR"] = os.getcwd()
    steps = _discover_pipeline()

    # Run immediately, then on schedule
    run_pipeline(steps)
    schedule.every().day.at("03:00").do(run_pipeline, steps)
    schedule.every().day.at("15:00").do(run_pipeline, steps)

    print("Scheduler running (Ctrl+C to stop)...")
    while True:
        schedule.run_pending()
        time.sleep(10)


if __name__ == "__main__":
    main()
