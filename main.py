"""Runs the whole pipeline with one command: python main.py"""

import logging
import time

from src import extract, transform

log = logging.getLogger("pipeline")

if __name__ == "__main__":
    start = time.perf_counter()
    extract.main()
    transform.main()
    log.info("Pipeline finished in %.1fs", time.perf_counter() - start)