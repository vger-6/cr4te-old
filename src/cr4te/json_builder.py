import logging
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable, TypeAlias, DefaultDict
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from pydantic import ValidationError

from .constants import CR4TE_JSON_FILE_NAME
from .utils import json_utils
from .utils import text_utils
from .utils import image_utils
from .utils.error_utils import format_build_failures
from .enums.orientation import Orientation
from .enums.domain import Domain
from .enums.creator_type import CreatorType
from .context.json_context import JsonBuildContext
from .validators.cr4te_schema import Creator as CreatorSchema, build_domain_meta
from .validators.global_state_schema import GlobalState

__all__ = ["build_creator_json_files", "clean_creator_json_files", "load_global_state", "save_global_state", "clean_global_state"]

logger = logging.getLogger(__name__)

ImageHandler: TypeAlias = Callable[[Path, Optional[Path]], tuple[Optional[Path], "ImageHandler"]]

IMAGE_EXTS = (".jpg", ".jpeg", ".png")
VIDEO_EXTS = (".mp4", ".m4v", ".mkv", ".webm")
AUDIO_EXTS = (".mp3", ".m4a")
DOC_EXTS = (".pdf",)
TEXT_EXTS = (".md",)

class InvalidDateFormatError(ValueError):
    pass

def _normalize_date(date_str: Optional[str]) -> str:
    """
    Validates and normalizes a date string.

    Accepts:
        - YYYY
        - YYYY-MM
        - YYYY-MM-DD

    Returns normalized string if valid.
    Returns "" if input is None or empty.
    Raises InvalidDateFormatError if format is invalid.
    """
    if date_str is None:
        return ""

    if not isinstance(date_str, str):
        raise InvalidDateFormatError(f"Expected string or None, got {type(date_str)}")

    date_str = date_str.strip()
    if not date_str:
        return ""

    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime(fmt)
        except ValueError:
            continue

    raise InvalidDateFormatError(f"Invalid date format: '{date_str}'")
    
def _safe_normalize_date(date_str: Optional[str], field_name: str, context_name: str) -> str:
    try:
        return _normalize_date(date_str)
    except InvalidDateFormatError as e:
        logger.warning(f"{context_name}: invalid {field_name}: {date_str} ({e})")
        return ""
        
def _is_excluded_path(path: Path, exclude_prefixes: tuple[str, ...]) -> bool:
    return any(part.startswith(exclude_prefixes) or part.startswith('.') for part in path.parts)
        
def _validate_creator(creator: Dict[str, Any], domain: Domain = Domain.CREATOR) -> None:
    try:
        CreatorSchema.model_validate(creator, context={"domain": domain})

    except ValidationError as e:
        name = creator.get("name", "<unknown>")
        error_lines = [f"[{name}] {err['loc'][0]}: {err['msg']}" for err in e.errors()]
        formatted = "\n".join(error_lines)
        raise ValueError(f"Validation failed for creator '{name}':\n{formatted}")
             
def _is_collaboration(name: str, separators: Optional[List[str]]) -> bool:
    if not separators:
        return False
    return any(sep in name for sep in separators)
    
def _load_existing_json(json_path: Path) -> Dict[str, Any]:
    if json_path.exists():
        return json_utils.load_json(json_path)
    return {}


class ImageSelector:
    def __init__(self, basename: str, orientation: Orientation, auto_find: bool = True):
        self.basename = basename
        self.orientation = orientation
        self.selected: Optional[Path] = None
        self._handler: ImageHandler = self._image_init if auto_find else self._image_by_name

    def consider(self, image_path: Path):
        self.selected, self._handler = self._handler(image_path, self.selected)

    # --- Handler methods ---
    def _image_init(self, image_path: Path, candidate: Optional[Path]) -> tuple[Optional[Path], ImageHandler]:
        stem = image_path.stem.lower()
        if stem == self.basename:
            return image_path, self._image_done
        elif image_utils.infer_image_orientation(image_path) == self.orientation:
            return image_path, self._image_by_name
        else:
            return candidate or image_path, self._image_init

    def _image_by_name(self, image_path: Path, candidate: Optional[Path]) -> tuple[Optional[Path], ImageHandler]:
        stem = image_path.stem.lower()
        if stem == self.basename:
            return image_path, self._image_done
        else:
            return candidate, self._image_by_name

    def _image_done(self, image_path: Path, candidate: Optional[Path]) -> tuple[Optional[Path], ImageHandler]:
        return candidate, self._image_done

@dataclass
class MediaBucket:
    ctx: JsonBuildContext
    is_root: bool
    portrait_selector: ImageSelector
    cover_selector: Optional[ImageSelector] = None
    videos: List[Dict[str, str]] = field(default_factory=list)
    tracks: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    documents: List[str] = field(default_factory=list)
    texts: List[str] = field(default_factory=list)

    def _find_video_poster(self, video_path: Path, input_dir: Path) -> Path | None:
        """
        Find an image in the same directory with the same stem as the video.
        Returns a Path relative to input_dir, or None if not found.
        """
        for img_ext in IMAGE_EXTS:
            candidate = video_path.with_suffix(img_ext)
            if candidate.exists():
                return candidate.relative_to(input_dir)
        return None
    
    def _is_video_poster_candidate(self, image_path: Path) -> bool:
        """
        Returns True if an image has a sibling video file with the same stem.
        """
        for vid_ext in VIDEO_EXTS:
            if image_path.with_suffix(vid_ext).exists():
                return True
        return False

    def add(self, media_path: Path) -> None:
        suffix = media_path.suffix.lower()
        stem = media_path.stem.lower()
        rel = media_path.relative_to(self.ctx.input_dir)

        if suffix in VIDEO_EXTS:
            poster = self._find_video_poster(media_path, self.ctx.input_dir)
            self.videos.append({
                "file": str(rel),
                "poster": str(poster) if poster else ""
            })

        elif suffix in AUDIO_EXTS:
            self.tracks.append(str(rel))

        elif suffix in IMAGE_EXTS and not self._is_video_poster_candidate(media_path):

            if stem not in (self.ctx.cover_basename, self.ctx.portrait_basename):
                self.images.append(str(rel))

            self.portrait_selector.consider(media_path)

            if self.cover_selector is not None:
                self.cover_selector.consider(media_path)

        elif suffix in DOC_EXTS:
            self.documents.append(str(rel))

        elif suffix in TEXT_EXTS and media_path.name.lower() != self.ctx.readme_file_name.lower():
            self.texts.append(str(rel))   

@dataclass
class CreatorMediaIndex:
    """
    Organizes media according to a 2-level hierarchy:

    input_dir/
        creator/
            <media>
            project/
                <media>
            <metadata_folder>/
                <metadata>

    Notes:
    - Files directly under a level OR inside its metadata folder are treated as "root"
    - Metadata folders are not treated as projects
    """

    CREATOR_DEPTH = 1
    PROJECT_DEPTH = 2

    def __init__(self, ctx: JsonBuildContext):
        self.ctx = ctx
        self.creator_media: Dict[Path, MediaBucket] = {}
        self.project_media: Dict[str, Dict[Path, MediaBucket]] = {}

        self.portrait_selector = ImageSelector(
            ctx.portrait_basename,
            Orientation.PORTRAIT,
            ctx.auto_find_portrait,
        )

        self.cover_selectors: DefaultDict[str, ImageSelector] = defaultdict(
            lambda: ImageSelector(ctx.cover_basename, Orientation.LANDSCAPE, True)
        )

    def _get_root_status(self, parts: tuple[str, ...], depth: int) -> bool:
        """
        A file is considered root if:
        - it is a direct child of the level, OR
        - it resides directly inside the metadata folder
        """
        is_direct_child = len(parts) == depth + 1
        is_in_metadata = (
            len(parts) > depth
            and parts[-2] == self.ctx.metadata_folder_name
        )
        return is_direct_child or is_in_metadata

    def _get_project_name(self, parts: tuple[str, ...]) -> Optional[str]:
        """Extract project name if present and not a metadata folder."""
        if len(parts) > self.PROJECT_DEPTH:
            candidate = parts[self.CREATOR_DEPTH]
            if candidate != self.ctx.metadata_folder_name:
                return candidate
        return None

    def _get_creator_bucket(self, rel_folder: Path, parts: tuple[str, ...]) -> MediaBucket:
        bucket = self.creator_media.get(rel_folder)
        if bucket is None:
            bucket = MediaBucket(
                self.ctx,
                self._get_root_status(parts, self.CREATOR_DEPTH),
                self.portrait_selector,
            )
            self.creator_media[rel_folder] = bucket
        return bucket

    def _get_project_bucket(self, project_name: str, rel_folder: Path, parts: tuple[str, ...]) -> MediaBucket:
        proj_dict = self.project_media.setdefault(project_name, {})
        bucket = proj_dict.get(rel_folder)

        if bucket is None:
            bucket = MediaBucket(
                self.ctx,
                self._get_root_status(parts, self.PROJECT_DEPTH),
                self.portrait_selector,
                self.cover_selectors[project_name],
            )
            proj_dict[rel_folder] = bucket

        return bucket

    def add_media(self, media_path: Path) -> None:
        rel_path = media_path.relative_to(self.ctx.input_dir)
        parts = rel_path.parts
        rel_folder = rel_path.parent

        project_name = self._get_project_name(parts)

        if project_name is None:
            bucket = self._get_creator_bucket(rel_folder, parts)
        else:
            bucket = self._get_project_bucket(project_name, rel_folder, parts)

        bucket.add(media_path)

    def get_selected_portrait(self) -> Optional[Path]:
        return self.portrait_selector.selected

    def get_selected_cover(self, project_name: str) -> Optional[Path]:
        return self.cover_selectors[project_name].selected
    
def _build_media_groups(media_dict: Dict[Path, MediaBucket], metadata_folder_name: str) -> List[Dict[str, Any]]:
    media_groups = []
    for rel_media_folder_path, media in media_dict.items():
       parts = rel_media_folder_path.parts
       media_groups.append({
            "is_root": media.is_root,
            "videos": sorted(media.videos, key=lambda v: v["file"]),
            "tracks": sorted(media.tracks),
            "images": sorted(media.images),
            "documents": sorted(media.documents),
            "texts": sorted(media.texts),
            "rel_dir_path": str(rel_media_folder_path)
        })
    return media_groups

def _iter_media_files(ctx, creator_dir):
    # Helper to check max depth
    def _is_within_search_depth(path: Path) -> bool:
        return ctx.max_search_depth is None or len(path.relative_to(creator_dir).parts) <= ctx.max_search_depth + 1
    
    for media_path in creator_dir.rglob("*"):
        if not media_path.is_file():
            continue

        if _is_excluded_path(media_path, (ctx.global_exclude_prefix,)):
            continue

        if not _is_within_search_depth(media_path):
            continue

        yield media_path

def _build_creator(
    ctx: JsonBuildContext,
    creator_dir: Path,
    domain: Domain,
    preserve_domain_meta: bool,
) -> Dict[str, Any]:
    media_index = CreatorMediaIndex(ctx)
    for media_path in _iter_media_files(ctx, creator_dir):
        media_index.add_media(media_path)

    creator_name = creator_dir.name
    existing_creator = _load_existing_json(creator_dir / CR4TE_JSON_FILE_NAME)
    existing_projects = { p["title"]: p for p in existing_creator.get("projects", []) if "title" in p }
    projects = []
    for project_name, folders in media_index.project_media.items():
        cover = media_index.get_selected_cover(project_name)
        existing_project = existing_projects.get(project_name, {})
        domain_meta = build_domain_meta(
            domain,
            existing_project.get("domain_meta", {}) if preserve_domain_meta else {},
        )
        projects.append({
            "title": project_name,
            "tags": existing_project.get("tags", []),
            "info": text_utils.read_text(creator_dir / project_name / ctx.readme_file_name) or existing_project.get("info", ""),
            "cover": str(cover.relative_to(ctx.input_dir)) if cover else "",
            "release_date": _safe_normalize_date(existing_project.get("release_date", ""), "release_date", f"{creator_name} - {project_name}"),
            "media_groups": _build_media_groups(folders, ctx.metadata_folder_name),
            "domain_meta": domain_meta,
        })
    
    separators = ctx.collaboration_separators
    creator_type = existing_creator.get("type")

    valid_creator_types = {creator_type.value for creator_type in CreatorType}
    if creator_type not in valid_creator_types:
        is_collab = _is_collaboration(creator_name, separators)
        creator_type = CreatorType.COLLABORATION.value if is_collab else CreatorType.PERSON.value
        members = [name.strip() for name in text_utils.multi_split(creator_name, separators)] if is_collab else []
    else:
        members = existing_creator.get("collaboration", {}).get("members", [])

    portrait = media_index.get_selected_portrait()
    
    # Build creator record
    creator = {
        "name": creator_name,
        "type": creator_type,
        "aliases": existing_creator.get("aliases", []),
        "collaborations": [],
        "tags": existing_creator.get("tags", []),
        "info": text_utils.read_text(creator_dir / ctx.readme_file_name) or existing_creator.get("info", ""),
        "portrait": str(portrait.relative_to(ctx.input_dir)) if portrait else "",
        "active_since": _safe_normalize_date(existing_creator.get("active_since", ""), "active_since", creator_name),
        "person": {
            "date_of_birth":  _safe_normalize_date(existing_creator.get("person", {}).get("date_of_birth", ""), "person.date_of_birth", creator_name),
            "date_of_death": _safe_normalize_date(existing_creator.get("person", {}).get("date_of_death", ""), "person.date_of_death", creator_name),
            "civil_name": existing_creator.get("person", {}).get("civil_name", ""),
          },
        "collaboration": {
            "founding_date":  _safe_normalize_date(existing_creator.get("collaboration", {}).get("founding_date", ""), "collaboration.founding_date", creator_name),
            "dissolution_date": _safe_normalize_date(existing_creator.get("collaboration", {}).get("dissolution_date", ""), "collaboration.dissolution_date", creator_name),
            "members": members,
          },
        "nationality": existing_creator.get("nationality", ""),
        "media_groups": _build_media_groups(media_index.creator_media, ctx.metadata_folder_name),
        "projects": projects,
    }
    
    return creator
    
def _link_creator_collaborations(collab_map: dict[str, dict[str, Any]]) -> None:
    """
    Builds reverse collaboration links and patches JSON files in-place.
    """
    reverse_map: dict[str, list[str]] = defaultdict(list)

    # Build reverse index: If it's a collab, notify the members
    for creator_name, info in collab_map.items():
        if info["type"] == CreatorType.COLLABORATION.value and info["members"]:
            for member in info["members"]:
                reverse_map[member].append(creator_name)

    valid_names = set(collab_map.keys())

    # Patch each creator JSON independently
    for creator_name, info in collab_map.items():
        # Only "person" types get the reverse "collaborations" list updated
        # Collaborations themselves don't usually list other collaborations they belong to here
        if info["type"] == CreatorType.COLLABORATION.value:
            continue

        json_path = info["dir"] / CR4TE_JSON_FILE_NAME
        existing = _load_existing_json(json_path)

        auto_collabs = reverse_map.get(creator_name, [])
        raw_manual = existing.get("collaborations", [])

        # Detect invalid
        invalid_collabs = sorted({
            name for name in raw_manual
            if name not in valid_names
        })

        if invalid_collabs:
            logger.warning(f"{creator_name} ({json_path}): removing invalid collaborations: {invalid_collabs}")

        # Keep only valid manual collaborations
        manual_collabs = [
            name for name in raw_manual
            if name in valid_names
        ]

        merged = sorted(set(auto_collabs + manual_collabs))

        if existing.get("collaborations") != merged:
            existing["collaborations"] = merged
            _write_creator_json(info["dir"], existing)

def _write_creator_json(creator_dir: Path, creator_data: Dict[str, Any]) -> None:
    json_path = creator_dir / CR4TE_JSON_FILE_NAME
    tmp_path = json_path.with_suffix(json_path.suffix + ".tmp")

    existing = _load_existing_json(json_path)
    if existing == creator_data:
        return

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(creator_data, f, indent=2)

    tmp_path.replace(json_path)
            
def build_creator_json_files(
    input_dir: Path,
    media_rules: dict[str, Any],
    domain: Domain = Domain.CREATOR,
    previous_domain: Optional[Domain] = None,
) -> None:
    ctx = JsonBuildContext(input_dir, media_rules)
    collab_map: dict[str, dict[str, Any]] = {}
    failures: List[tuple[str, Exception]] = []
    preserve_domain_meta = previous_domain is None or previous_domain == domain

    for creator_dir in sorted(ctx.input_dir.iterdir()):
        if not creator_dir.is_dir() or _is_excluded_path(creator_dir, (ctx.global_exclude_prefix,)):
            continue
            
        try:
            logger.info(f"Processing: {creator_dir.name}")
            creator_data = _build_creator(ctx, creator_dir, domain, preserve_domain_meta)
            _validate_creator(creator_data, domain)
            _write_creator_json(creator_dir, creator_data)
            
            collab_map[creator_data["name"]] = {
                "dir": creator_dir,
                "members": creator_data.get("collaboration", {}).get("members", []),
                "type": creator_data.get("type"), 
            }
            
        except Exception as e:
            logger.exception(f"{creator_dir.name}: failed to process")
            failures.append((creator_dir.name, e))
            continue

    _link_creator_collaborations(collab_map)

    if failures:
        logger.error(
            "JSON build completed with %s succeeded creator(s) and %s failed creator(s).",
            len(collab_map),
            len(failures),
        )
        raise ValueError(format_build_failures("JSON build", failures))
    
def clean_creator_json_files(input_dir: Path, dry_run: bool = False) -> None:
    total = 0
    deleted = 0
    skipped = 0

    for creator_dir in input_dir.iterdir():
        if not creator_dir.is_dir():
            continue

        json_path = creator_dir / CR4TE_JSON_FILE_NAME
        if json_path.exists():
            total += 1
            logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Deleting: {json_path}")
            if not dry_run:
                try:
                    json_path.unlink()
                    deleted += 1
                except Exception as e:
                    logger.error(f"Deleting {json_path}: {e}")
                    skipped += 1
        else:
            continue

    logger.info(
        f"\nSummary:\n"
        f"\tTotal {CR4TE_JSON_FILE_NAME} files found: {total}\n"
        f"\tDeleted: {deleted}\n"
        f"\tSkipped/errors: {skipped}"
        )
        
    if dry_run:
        logger.info("\t(Dry-run mode: no files were deleted)")

# === Global state functions ===

def _get_global_json_file_path(input_dir: Path) -> Path:
    """
    Returns the path to the global cr4te.json file in the input directory.
    """
    return input_dir / CR4TE_JSON_FILE_NAME

def load_global_state(input_dir: Path) -> Optional[GlobalState]:
    """
    Loads the global cr4te.json (state) from the input directory.
    Returns None if the file doesn't exist.
    """
    global_state_path = _get_global_json_file_path(input_dir)
    if global_state_path.exists():
        try:
            return GlobalState.model_validate(json_utils.load_json(global_state_path))
        except Exception as e:
            logger.warning(f"Invalid global state in {global_state_path}, ignoring: {e}")
    return None

def save_global_state(input_dir: Path, domain: Optional[Domain]) -> None:
    """
    Saves the domain setting to the global cr4te.json file in the input directory.
    """
    global_state_path = _get_global_json_file_path(input_dir)
    existing = {}
    
    if global_state_path.exists():
        try:
            existing = json_utils.load_json(global_state_path)
        except Exception as e:
            logger.warning(f"Could not load existing global state from {global_state_path}: {e}")

    state = GlobalState(domain=domain).model_dump(mode="json")

    if existing == state:
        logger.debug(f"Global state is unchanged, not writing to {global_state_path}")
        return
    
    tmp_path = global_state_path.with_suffix(".tmp")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)

    tmp_path.replace(global_state_path)

def clean_global_state(input_dir: Path, dry_run: bool = False) -> bool:
    """
    Deletes the global cr4te.json file from the input directory.
    Returns True if deleted (or not found in dry-run), False on error.
    """
    global_state_path = _get_global_json_file_path(input_dir)
    if not global_state_path.exists():
        return True
    
    logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Deleting: {global_state_path}")
    if dry_run:
        return True
    
    try:
        global_state_path.unlink()
        return True
    except Exception as e:
        logger.error(f"Deleting {global_state_path}: {e}")
        return False
