"""
CLI script to setup or update Azure AI Search resources (DataSource, Index, Skillset, Indexer).
Usage:
    python -m worker.scripts.setup_search_pipeline
or from within worker/:
    python scripts/setup_search_pipeline.py
"""
import sys
import os

# Add worker directory to sys.path so imports like `config` and `services` resolve cleanly
current_dir = os.path.dirname(os.path.abspath(__file__))
worker_dir = os.path.abspath(os.path.join(current_dir, ".."))
if worker_dir not in sys.path:
    sys.path.insert(0, worker_dir)

from services.search_indexer import SearchPipelineSetupService


def main():
    service = SearchPipelineSetupService()
    service.setup_pipeline()


if __name__ == "__main__":
    main()
