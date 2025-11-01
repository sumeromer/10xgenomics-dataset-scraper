#!/usr/bin/env python3
"""
10X Genomics Data Pipeline Orchestrator

Master orchestrator that runs scraper and validator agents in sequence.
Manages the complete data pipeline from scraping to validation.
"""

import sys
import os
import subprocess
import argparse
import yaml
from pathlib import Path
from datetime import datetime
import json


class PipelineOrchestrator:
    """Orchestrates the multi-agent data pipeline."""

    def __init__(self, config_path='config.yml', url=None, name=None):
        """
        Initialize the orchestrator.

        Args:
            config_path: Path to pipeline configuration file
            url: Source URL to scrape (overrides config default)
            name: Human-readable run identifier (overrides config default)
        """
        self.config_path = Path(config_path)
        self.root_dir = Path(__file__).parent
        self.log_dir = self.root_dir / 'logs'
        self.log_dir.mkdir(exist_ok=True)

        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = self.log_dir / f"pipeline_{self.timestamp}.log"

        self.load_config()

        # Set URL and name from parameters or config defaults
        self.url = url or self.config.get('pipeline', {}).get('default_url', '')
        self.name = name or self.config.get('pipeline', {}).get('default_name', '10XGenomics-Dataset')
        self.base_output_dir = Path(self.config.get('pipeline', {}).get('base_output_dir', './output'))

        self.results = {
            "pipeline_start": datetime.now().isoformat(),
            "url": self.url,
            "name": self.name,
            "agents": {},
            "overall_status": "unknown"
        }

    def load_config(self):
        """Load pipeline configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            print(f"✓ Loaded configuration from {self.config_path}")
        except FileNotFoundError:
            print(f"✗ Config file not found: {self.config_path}")
            print("Using default configuration...")
            self.config = self.get_default_config()
        except Exception as e:
            print(f"✗ Error loading config: {e}")
            sys.exit(2)

    def get_default_config(self):
        """Return default pipeline configuration."""
        return {
            'pipeline': {
                'name': '10X Genomics Data Pipeline',
                'agents': [
                    {
                        'name': 'scraper',
                        'script': 'skills/scraper/scraper.py',
                        'enabled': True
                    },
                    {
                        'name': 'validator',
                        'script': 'skills/validator/validator.py',
                        'enabled': True,
                        'depends_on': 'scraper'
                    },
                    {
                        'name': 'metadata_enricher',
                        'script': 'skills/metadata_enricher/metadata_enricher.py',
                        'enabled': True,
                        'depends_on': 'validator'
                    }
                ]
            },
            'validation': {
                'file_consistency': True,
                'url_verification': True,
                'max_retries': 3,
                'report_format': ['json', 'html']
            },
            'enrichment': {
                'enabled': True,
                'max_retries': 3,
                'timeout': 30,
                'parallel_workers': 3
            }
        }

    def update_timestamp(self, task_name):
        """
        Update timestamp for a specific task in timestamp.txt file.

        Args:
            task_name: Name of the task (e.g., 'scraper', 'validator', 'metadata-enricher')
        """
        timestamp_file = self.base_output_dir / self.name / 'timestamp.txt'
        timestamp_file.parent.mkdir(parents=True, exist_ok=True)

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Define all possible tasks
        all_tasks = ['scraper', 'validator', 'metadata-enricher']

        # Read existing timestamps or initialize
        timestamps = {}
        if timestamp_file.exists():
            with open(timestamp_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[1:]:  # Skip header
                    line = line.strip()
                    if line and '\t' in line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            timestamps[parts[0].strip()] = parts[1].strip()

        # Update the specific task
        timestamps[task_name] = current_time

        # Write back with pretty formatting
        with open(timestamp_file, 'w', encoding='utf-8') as f:
            # Header
            f.write(f"{'task':<24}\ttime\n")
            # Task lines
            for task in all_tasks:
                time_str = timestamps.get(task, '')
                f.write(f"{task:<24}\t{time_str}\n")

    def log(self, message, to_file=True):
        """
        Log a message to stdout and optionally to log file.

        Args:
            message: Message to log
            to_file: Whether to write to log file
        """
        print(message)
        if to_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"{message}\n")

    def run_agent(self, agent_config):
        """
        Run a single agent.

        Args:
            agent_config: Agent configuration dictionary

        Returns:
            Dictionary with agent execution results
        """
        agent_name = agent_config['name']
        script_path = self.root_dir / agent_config['script']

        result = {
            'name': agent_name,
            'start_time': datetime.now().isoformat(),
            'exit_code': None,
            'status': 'unknown',
            'duration': None
        }

        self.log(f"\n{'='*60}")
        self.log(f"Running Agent: {agent_name.upper()}")
        self.log(f"Script: {script_path}")
        self.log(f"{'='*60}")

        if not script_path.exists():
            self.log(f"✗ Script not found: {script_path}")
            result['status'] = 'error'
            result['exit_code'] = 2
            result['error'] = f"Script not found: {script_path}"
            return result

        try:
            start_time = datetime.now()

            # Build command with URL and name parameters
            cmd = [sys.executable, str(script_path)]

            # Add common parameters for all agents
            if agent_name == 'scraper':
                cmd.extend(['--url', self.url, '--name', self.name, '--base-output-dir', str(self.base_output_dir)])
            elif agent_name in ['validator', 'metadata_enricher']:
                cmd.extend(['--name', self.name, '--base-output-dir', str(self.base_output_dir)])

            # Run the agent script with real-time output streaming
            # This allows progress bars and live updates to display properly
            process = subprocess.run(
                cmd,
                text=True,
                cwd=str(script_path.parent),
                # Don't capture output - let it stream directly to terminal
                stdout=None,
                stderr=None
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            result['exit_code'] = process.returncode
            result['end_time'] = end_time.isoformat()
            result['duration'] = f"{duration:.2f}s"

            # Determine status
            if process.returncode == 0:
                result['status'] = 'success'
                self.log(f"\n✓ Agent {agent_name} completed successfully in {duration:.2f}s")

                # Update timestamp for successful completion
                # Convert agent name to timestamp format (e.g., 'metadata_enricher' -> 'metadata-enricher')
                timestamp_task_name = agent_name.replace('_', '-')
                self.update_timestamp(timestamp_task_name)

            elif process.returncode == 1:
                result['status'] = 'failed'
                self.log(f"\n✗ Agent {agent_name} failed with validation errors")
            else:
                result['status'] = 'error'
                self.log(f"\n✗ Agent {agent_name} encountered a critical error (exit code: {process.returncode})")

        except Exception as e:
            result['status'] = 'error'
            result['exit_code'] = 2
            result['error'] = str(e)
            self.log(f"\n✗ Exception running agent {agent_name}: {e}")

        return result

    def run_pipeline(self, skip_scraping=False, skip_validation=False, skip_enrichment=False):
        """
        Run the complete pipeline.

        Args:
            skip_scraping: Skip the scraper agent
            skip_validation: Skip the validator agent
            skip_enrichment: Skip the metadata enricher agent

        Returns:
            Overall pipeline status
        """
        self.log("="*60)
        self.log(f"PIPELINE: {self.config['pipeline']['name']}")
        self.log(f"Started: {self.timestamp}")
        self.log("="*60)

        agents = self.config['pipeline']['agents']
        overall_success = True

        for agent_config in agents:
            agent_name = agent_config['name']

            # Check if agent is enabled
            if not agent_config.get('enabled', True):
                self.log(f"\n⊘ Agent {agent_name} is disabled, skipping...")
                continue

            # Check skip flags
            if agent_name == 'scraper' and skip_scraping:
                self.log(f"\n⊘ Skipping scraper agent (--skip-scraping flag)")
                self.results['agents'][agent_name] = {
                    'status': 'user_skipped',
                    'reason': 'User requested skip'
                }
                continue

            if agent_name == 'validator' and skip_validation:
                self.log(f"\n⊘ Skipping validator agent (--skip-validation flag)")
                self.results['agents'][agent_name] = {
                    'status': 'user_skipped',
                    'reason': 'User requested skip'
                }
                continue

            if agent_name == 'metadata_enricher' and skip_enrichment:
                self.log(f"\n⊘ Skipping metadata enricher agent (--skip-enrichment flag)")
                self.results['agents'][agent_name] = {
                    'status': 'user_skipped',
                    'reason': 'User requested skip'
                }
                continue

            # Check dependencies
            depends_on = agent_config.get('depends_on')
            if depends_on:
                dep_result = self.results['agents'].get(depends_on, {})
                dep_status = dep_result.get('status', 'unknown')

                # Only block dependent agents if the dependency failed or errored
                # Allow dependents to run if dependency was user-skipped (assumes data exists from previous runs)
                if dep_status in ['failed', 'error']:
                    self.log(f"\n✗ Skipping {agent_name} (dependency {depends_on} failed)")
                    self.results['agents'][agent_name] = {
                        'status': 'skipped',
                        'reason': f'Dependency {depends_on} failed'
                    }
                    overall_success = False
                    continue
                elif dep_status == 'user_skipped':
                    self.log(f"\n→ Continuing with {agent_name} (dependency {depends_on} was user-skipped, assuming data exists)")
                elif dep_status not in ['success', 'user_skipped']:
                    self.log(f"\n✗ Skipping {agent_name} (dependency {depends_on} status: {dep_status})")
                    self.results['agents'][agent_name] = {
                        'status': 'skipped',
                        'reason': f'Dependency {depends_on} status: {dep_status}'
                    }
                    overall_success = False
                    continue

            # Run the agent
            result = self.run_agent(agent_config)
            self.results['agents'][agent_name] = result

            # Check if agent failed
            if result['status'] != 'success':
                overall_success = False
                # Stop pipeline on critical errors
                if result['exit_code'] == 2:
                    self.log("\n✗ Critical error encountered, stopping pipeline")
                    break

        # Pipeline summary
        self.results['pipeline_end'] = datetime.now().isoformat()
        self.results['overall_status'] = 'success' if overall_success else 'failed'

        self.log("\n" + "="*60)
        self.log("PIPELINE SUMMARY")
        self.log("="*60)

        for agent_name, result in self.results['agents'].items():
            status_icon = {
                'success': '✓',
                'failed': '✗',
                'error': '✗',
                'skipped': '⊘',
                'user_skipped': '⊘'
            }.get(result.get('status'), '?')

            duration = result.get('duration', 'N/A')
            self.log(f"{status_icon} {agent_name}: {result.get('status', 'unknown').upper()} ({duration})")

        self.log("\n" + "="*60)
        self.log(f"Overall Status: {self.results['overall_status'].upper()}")
        self.log(f"Log saved to: {self.log_file}")
        self.log("="*60)

        # Save results as JSON
        results_file = self.log_dir / f"pipeline_results_{self.timestamp}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2)
        self.log(f"Results saved to: {results_file}")

        return 0 if overall_success else 1


def main():
    """Main entry point for the orchestrator."""
    parser = argparse.ArgumentParser(
        description='10X Genomics Data Pipeline Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline with custom URL and name
  python orchestrator.py --url "https://..." --name "10XGenomics-VisiumHD-Human"

  # Run with defaults from config.yml
  python orchestrator.py

  # Skip scraping, only validate and enrich existing data
  python orchestrator.py --skip-scraping --name "10XGenomics-VisiumHD-Human"

  # Run different dataset
  python orchestrator.py --url "https://..." --name "10XGenomics-Xenium-Mouse"

  # Use custom config file
  python orchestrator.py --config my_config.yml --url "..." --name "..."
        """
    )

    parser.add_argument('--url', type=str,
                       help='Source URL to scrape (overrides config default)')
    parser.add_argument('--name', type=str,
                       help='Human-readable run identifier (overrides config default)')
    parser.add_argument('--skip-scraping', action='store_true',
                       help='Skip the scraper agent')
    parser.add_argument('--skip-validation', action='store_true',
                       help='Skip the validator agent')
    parser.add_argument('--skip-enrichment', action='store_true',
                       help='Skip the metadata enricher agent')
    parser.add_argument('--config', default='config.yml',
                       help='Path to configuration file (default: config.yml)')

    args = parser.parse_args()

    # Initialize and run orchestrator
    orchestrator = PipelineOrchestrator(
        config_path=args.config,
        url=args.url,
        name=args.name
    )
    exit_code = orchestrator.run_pipeline(
        skip_scraping=args.skip_scraping,
        skip_validation=args.skip_validation,
        skip_enrichment=args.skip_enrichment
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
