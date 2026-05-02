import logging
import argparse
import webbrowser
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from importlib.metadata import version, PackageNotFoundError

from .config_manager import load_config, apply_cli_overrides
from .enums.image_sample_strategy import ImageSampleStrategy
from .enums.portrait_strategy import PortraitStrategy
from .enums.domain import Domain
from .html_builder import clear_output_folder, build_html_pages
from .json_builder import build_creator_json_files, clean_creator_json_files, load_global_state, save_global_state, clean_global_state

# Short flags
FLAG_INPUT_SHORT = "-i"
FLAG_OUTPUT_SHORT = "-o"

# Long Flags
FLAG_INPUT = "--input"
FLAG_OUTPUT = "--output"
FLAG_OPEN = "--open"
FLAG_FORCE = "--force"
FLAG_CLEAN = "--clean"

def _setup_logging():
    """Configures the global logging settings."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr
    )

def _load_config(rel_config_path_arg: str) -> Dict[str, Any]:
    config_path = Path(rel_config_path_arg).resolve() if rel_config_path_arg else None
    return load_config(config_path)
    
def _confirm_action(prompt: str, force: bool = False) -> bool:
    if force:
        return True
    confirm = input(f"{prompt} [y/N]: ").strip().lower()
    return confirm == 'y'
    
def _apply_cli_overrides_from_args(config: dict, args, domain: Optional[Domain] = None) -> dict:
    resolved_domain = domain if domain is not None else (Domain(args.domain) if getattr(args, "domain", None) else None)
    return apply_cli_overrides(
        config,
        image_sample_strategy=ImageSampleStrategy(args.image_sample_strategy) if args.image_sample_strategy else None,
        portrait_strategy=PortraitStrategy(args.portrait_strategy) if args.portrait_strategy else None,
        domain=resolved_domain
    )

def _resolve_domain(cli_domain: Optional[Domain], saved_domain: Optional[Domain], force: bool) -> Domain:
    default_domain = Domain.CREATOR

    if cli_domain is None:
        return saved_domain if saved_domain else default_domain

    if saved_domain is None:
        logging.info(f"Domain set to '{cli_domain.value}'.")
        return cli_domain

    if cli_domain == saved_domain:
        return cli_domain

    prompt = (
        f"You are switching from domain '{saved_domain.value}' "
        f"to '{cli_domain.value}'.\n\n"
        "WARNING: this may permanently invalidate saved input data in cr4te.json files.\n\n"
        "Do you want to continue?"
    )

    if _confirm_action(prompt, force=force):
        logging.info(f"Domain set to '{cli_domain.value}'.")
        return cli_domain

    logging.info(f"Keeping domain '{saved_domain.value}'.")
    return saved_domain

def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Media Organizer CLI")
    
    try:
        __version__ = version("cr4te")
    except PackageNotFoundError:
        __version__ = "0.0.0"
    
    parser.add_argument("-v", "--version", action="version", version=f"cr4te v{__version__}")
    
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _add_config_arguments(p: argparse.ArgumentParser):
        p.add_argument("--config", help="Path to configuration file (optional)")
        p.add_argument("--domain", choices=[m.value for m in Domain], help="Apply a domain-specific configuration preset")
        p.add_argument("--image-sample-strategy", choices=[s.value for s in ImageSampleStrategy], help="Strategy to sample images per folder")
        p.add_argument("--portrait-strategy", choices=[s.value for s in PortraitStrategy], help="Strategy to find portraits")

    # Build subcommand
    build_parser = subparsers.add_parser("build", help="Generate JSON metadata and build HTML site")
    build_parser.add_argument(FLAG_INPUT_SHORT, FLAG_INPUT, required=True, help="Path to the Creators folder")
    build_parser.add_argument(FLAG_OUTPUT_SHORT, FLAG_OUTPUT, required=True, help="Path to the HTML output folder")
    _add_config_arguments(build_parser)
    build_parser.add_argument(FLAG_OPEN, action="store_true", help="Open index.html after building")
    build_parser.add_argument(FLAG_FORCE, action="store_true", help="Force delete output folder")
    build_parser.add_argument(FLAG_CLEAN, action="store_true", help=f"Also delete thumbnails folder (with {FLAG_FORCE})")

    # Print-config
    print_config_parser = subparsers.add_parser("print-config", help="Print resolved configuration")
    _add_config_arguments(print_config_parser)

    # Clean-json
    clean_parser = subparsers.add_parser("clean-json", help="Delete cr4te.json files from all creator folders")
    clean_parser.add_argument(FLAG_INPUT_SHORT, FLAG_INPUT, required=True, help="Path to input folder containing creators")
    clean_parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without removing anything")
    clean_parser.add_argument(FLAG_FORCE, action="store_true", help="Actually delete files instead of showing a preview")

    return parser
    
def _build_cmd_handler(args):
    config = _load_config(args.config)

    input_dir = Path(args.input).resolve()
    if not input_dir.is_dir():
        logging.info(f"Input path does not exist or is not a directory: {input_dir}")
        logging.info("Aborting.")
        return

    # Load validated global state to get saved domain
    global_state = load_global_state(input_dir)
    saved_domain = global_state.domain if global_state else None

    cli_domain = Domain(args.domain) if args.domain else None
    final_domain = _resolve_domain(cli_domain, saved_domain, args.force)

    # Apply CLI overrides with the resolved domain
    config = _apply_cli_overrides_from_args(config, args, domain=final_domain)

    output_dir = Path(args.output).resolve()

    if output_dir.exists():
        if args.clean:
            msg = f"This will delete all output in '{output_dir}', including thumbnails. Continue?"
        else:
            msg = f"Clear existing output except thumbnails in '{output_dir}'?"

        if not _confirm_action(msg, force=args.force):
            logging.info("Aborting.")
            return

        clear_output_folder(output_dir, args.clean)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    logging.info("Building JSON metadata...")
    build_creator_json_files(input_dir, config["media_rules"], final_domain, saved_domain)

    logging.info("Building HTML site...")
    index_html_path = build_html_pages(input_dir, output_dir, config["site"], final_domain)

    save_global_state(input_dir, final_domain)

    if args.open:
        logging.info("Opening index.html...")
        webbrowser.open(f"file://{index_html_path.resolve()}")
        # TODO: Test if this call works in different OS -> webbrowser.open(index_html_path.resolve().as_uri())
        
def _print_config_cmd_handler(args):
    config = _load_config(args.config)
    config = _apply_cli_overrides_from_args(config, args)
    print(json.dumps(config, indent=4))

def _clean_json_cmd_handler(args):
    input_dir = Path(args.input).resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        logging.info(f"Input path does not exist or is not a directory: {input_dir}")
        logging.info("Aborting.")
        return

    if not args.dry_run and not _confirm_action(f"Delete all cr4te.json files in '{input_dir}'?", force=args.force):
        logging.info("Aborting.")
        return

    clean_creator_json_files(input_dir, dry_run=args.dry_run)
    clean_global_state(input_dir, dry_run=args.dry_run)

def main():
    _setup_logging()
    
    parser = _create_parser()
    args = parser.parse_args()
    
    command_map = {
        "build": _build_cmd_handler,
        "print-config": _print_config_cmd_handler,
        "clean-json": _clean_json_cmd_handler,
    }
    
    command_func = command_map.get(args.command)
    if not command_func:
        parser.print_help()
        return
    
    try:
        command_func(args)
    except ValueError as e:
        parser.error(str(e))

if __name__ == "__main__":
    main()

