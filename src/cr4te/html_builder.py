import logging
import shutil
import os
from pathlib import Path
from enum import Enum
from typing import List, Dict, Any, Optional, Iterable, Set, Tuple, Sequence
from datetime import datetime
from collections import defaultdict

from PIL import Image
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import ValidationError

from .constants import (
    CR4TE_CSS_DIR,
    CR4TE_JS_DIR,
    CR4TE_TEMPLATES_DIR,
    CR4TE_JSON_FILE_NAME
)

from .utils import path_utils
from .utils import text_utils
from .utils import image_utils
from .utils import date_utils
from .utils import json_utils
from .utils import audio_utils
from .utils.error_utils import format_build_failures
from .enums.domain import Domain
from .enums.media_type import MediaType
from .enums.thumb_type import ThumbType
from .enums.image_sample_strategy import ImageSampleStrategy
from .enums.image_gallery_building_strategy import ImageGalleryBuildingStrategy
from .enums.orientation import Orientation
from .enums.visible_fields import CreatorField, ProjectField
from .enums.creator_type import CreatorType
from .context.html_context import HtmlBuildContext, THUMBNAILS_DIRNAME
from .validators.cr4te_schema import Creator as CreatorSchema, get_domain_meta_fields, get_domain_meta_model

__all__ = ["clear_output_folder", "build_html_pages"]

logger = logging.getLogger(__name__)


class RenderMode(str, Enum):
    INLINE = "inline"
    LIST = "list"


DOMAIN_META_CONFIG_OVERRIDES = {
    Domain.MODEL: {
        "makeup_artists": {"label": "Makeup Artists"},
    },
    Domain.BOOK: {
        "isbns": {"label": "ISBNs"},
        "citations": {"label": "Citations"},
        "cover_artists": {"label": "Cover Artists"},
    },
    Domain.FILM: {
        "actors": {"label": "Cast", "render": RenderMode.LIST},
        "score_composers": {"label": "Score Composers"},
        "visual_effects": {"label": "Visual Effects"},
        "costume_designers": {"label": "Costume Designers"},
    },
    Domain.MUSIC: {
        "cover_artists": {"label": "Cover Artists"},
    },
    Domain.ART: {},
}


def _default_domain_meta_config(domain: Domain) -> Dict[str, Dict[str, str]]:
    return {
        field_name: {
            "label": field_name.replace("_", " ").title(),
            "render": RenderMode.INLINE,
        }
        for field_name in get_domain_meta_model(domain).model_fields
    }


def _validate_domain_meta_config_overrides() -> None:
    for domain, field_config in DOMAIN_META_CONFIG_OVERRIDES.items():
        invalid_keys = set(field_config) - get_domain_meta_fields(domain)
        if invalid_keys:
            keys = ", ".join(sorted(invalid_keys))
            raise ValueError(f"DOMAIN_META_CONFIG_OVERRIDES contains invalid keys for domain {domain.value}: {keys}")


def _build_domain_meta_config() -> Dict[Domain, Dict[str, Dict[str, str]]]:
    _validate_domain_meta_config_overrides()
    config = {}

    for domain in Domain:
        domain_config = _default_domain_meta_config(domain)
        for field_name, field_overrides in DOMAIN_META_CONFIG_OVERRIDES.get(domain, {}).items():
            domain_config[field_name].update({
                key: RenderMode(value) if key == "render" else value
                for key, value in field_overrides.items()
            })
        config[domain] = domain_config

    return config


DOMAIN_META_CONFIG = _build_domain_meta_config()

DEFAULT_CREATOR_FIELD_ORDER = [
    CreatorField.CIVIL_NAME,
    CreatorField.ALIASES,
    CreatorField.MEMBERS,
    CreatorField.DATE_OF_BIRTH,
    CreatorField.DATE_OF_DEATH,
    CreatorField.FOUNDING_DATE,
    CreatorField.DISSOLUTION_DATE,
    CreatorField.NATIONALITY,
    CreatorField.DEBUT_AGE,
    CreatorField.AGE_AT_TIME,
    CreatorField.ACTIVE_SINCE,
]

# Setup Jinja2 environment
env = Environment(
    loader=FileSystemLoader(str(CR4TE_TEMPLATES_DIR)),
    autoescape=select_autoescape(['html', 'xml'])
)
env.globals["MediaType"] = MediaType

FILE_TREE_DEPTH = 4

# HTML files live inside: output_dir/html/<depth levels>/<file.html>
# So to get back to output_dir, we need (depth + 1) "../" segments
HTML_PATH_TO_ROOT = path_utils.get_path_to_root(FILE_TREE_DEPTH + 1)


def _build_rel_creator_html_path(creator: Dict) -> Path:
    return path_utils.build_unique_path(Path('creator', creator['name']).with_suffix(".html"), FILE_TREE_DEPTH)


def _build_rel_project_html_path(creator: Dict, project: Dict) -> Path:
    return path_utils.build_unique_path(Path('project', creator['name'], project['title']).with_suffix(".html"), FILE_TREE_DEPTH)


def _get_or_create_thumbnail(ctx: HtmlBuildContext, rel_image_path: Path, thumb_type: ThumbType) -> Path:
    thumb_path = ctx.thumbs_dir / path_utils.build_unique_path(rel_image_path)
    thumb_path = path_utils.tag_path(thumb_path, thumb_type.value)

    if not thumb_path.exists():
        try:
            thumb = image_utils.generate_thumbnail(ctx.input_dir / rel_image_path, ctx.get_thumb_height(thumb_type))
            thumb_path.parent.mkdir(parents=True, exist_ok=True)

            thumb_ext = thumb_path.suffix.lower()
            match thumb_ext:
                case '.jpg' | '.jpeg':
                    format = 'JPEG'
                case '.png':
                    format = 'PNG'
                case _:
                    raise ValueError(f"Unsupported thumbnail extension: {thumb_ext}")

            thumb.save(thumb_path, format=format)

        except Exception as e:
            logger.error(f"Error creating thumbnail for {rel_image_path}: {e}")

    return thumb_path


def _resolve_thumbnail_or_default(ctx: HtmlBuildContext, rel_image_path: Optional[str], thumb_type: ThumbType) -> Path:
    """
    Returns the resolved thumbnail path for a given relative image path,
    falling back to a default image if the input is None or missing.
    """
    if rel_image_path:
        return _get_or_create_thumbnail(ctx, Path(rel_image_path), thumb_type)
    return ctx.get_default_thumb_path(thumb_type)


def _get_image_dimensions(path: Path) -> Dict[str, int]:
    """Return width and height for the given image path."""
    try:
        with Image.open(path) as img:
            return {
                "image_wrapper_width": img.width,
                "image_wrapper_height": img.height,
            }
    except Exception as e:
        logger.warning(f"Unable to read image dimensions for {path}: {e}")
        return {
            "image_wrapper_width": 0,
            "image_wrapper_height": 0,
        }


def _build_thumbnail_context(ctx: HtmlBuildContext, rel_image_path: Optional[str], thumb_type: ThumbType) -> Dict[str, Any]:
    thumb_path = _resolve_thumbnail_or_default(ctx, rel_image_path, thumb_type)
    rel_thumbnail_path = path_utils.relative_path_from(thumb_path, ctx.output_dir).as_posix()
    dimensions = _get_image_dimensions(thumb_path)

    return {
        "rel_thumbnail_path": rel_thumbnail_path,
        "image_wrapper_width": dimensions["image_wrapper_width"],
        "image_wrapper_height": dimensions["image_wrapper_height"],
    }


def _sample_images(rel_image_paths: List[str], max_images: int, strategy: ImageSampleStrategy) -> List[str]:
    if max_images <= 0:
        return []

    sorted_paths = sorted(rel_image_paths)

    match strategy:
        case ImageSampleStrategy.NONE:
            return []
        case ImageSampleStrategy.ALL:
            return sorted_paths
        case _ if len(sorted_paths) <= max_images:
            return sorted_paths
        case ImageSampleStrategy.HEAD:
            return sorted_paths[:max_images]
        case ImageSampleStrategy.SPREAD:
            step = len(sorted_paths) / max_images
            return [sorted_paths[int(i * step)] for i in range(max_images)]
        case _:
            return sorted_paths


def _sort_project(project: Dict) -> tuple:
    release_date = project["release_date"]
    has_date = bool(release_date)
    date_value = date_utils.parse_date(release_date) if has_date else datetime.max
    title = project["title"].lower()
    return (not has_date, date_value, title)


def _build_project_search_text(project: Dict, creator_name: str = "") -> str:
    search_terms = [project["title"]]
    search_terms.extend(project["tags"])

    if creator_name:
        search_terms.append(creator_name)

    return " ".join(search_terms).lower()


def _normalize_domain_meta_value(value: Any) -> List[str] | None:
    if value is None:
        return None

    if isinstance(value, list):
        normalized_list = [str(item).strip() for item in value if str(item).strip()]
        return normalized_list or None

    return None


def _build_meta_entry(label: str, value: Any, render: RenderMode = RenderMode.INLINE, url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if value is None:
        return None

    if isinstance(value, list):
        normalized_value = [str(item).strip() for item in value if str(item).strip()]
    else:
        normalized = str(value).strip()
        normalized_value = [normalized] if normalized else []

    if not normalized_value:
        return None

    entry = {
        "label": label.strip(),
        "value": normalized_value,
        "render": render.value,
    }

    if not entry["label"]:
        return None

    if url:
        entry["url"] = url

    return entry


def _compact_meta_entries(entries: Iterable[Optional[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    return [
        entry for entry in entries
        if entry and entry.get("label") and entry.get("value") and entry.get("render")
    ]


def _build_domain_meta_entries(domain: Domain, domain_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries = []
    config = DOMAIN_META_CONFIG.get(domain, {})

    for field_name in get_domain_meta_model(domain).model_fields:
        raw_value = domain_meta.get(field_name)
        normalized_value = _normalize_domain_meta_value(raw_value)
        if not normalized_value:
            continue

        field_config = config.get(field_name, {})
        label = field_config.get("label") or field_name.replace("_", " ").title()
        render_mode = field_config.get("render", RenderMode.INLINE)

        entries.append({
            "label": label,
            "value": normalized_value,
            "render": render_mode.value,
        })

    return entries


def _build_project_meta_entries(domain: Domain, project: Dict[str, Any], release_date: str) -> List[Dict[str, Any]]:
    entries = [_build_meta_entry("Title", project["title"])]

    if release_date:
        entries.append(_build_meta_entry("Release Date", release_date))

    entries.extend(_build_domain_meta_entries(domain, project.get("domain_meta", {})))
    return _compact_meta_entries(entries)


def _compute_media_counts(media_groups: List[Dict]) -> Dict[str, int]:
    """
    Computes total media counts from all media groups in a project.
    Returns a dictionary with counts for each media type.
    """
    counts = {
        "video": 0,
        "audio": 0,
        "image": 0,
        "document": 0,
        "text": 0,
    }
    for group in media_groups:
        counts["video"] += len(group.get("videos") or [])
        counts["audio"] += len(group.get("tracks") or [])
        counts["image"] += len(group.get("images") or [])
        counts["document"] += len(group.get("documents") or [])
        counts["text"] += len(group.get("texts") or [])
    return counts


def _compute_creator_stats(creator: Dict) -> Dict[str, Any]:
    """
    Computes stats for a creator: number of projects and total media counts.
    Returns a dictionary with project_count and media_counts.
    """
    project_count = len(creator.get("projects", []))
    
    # Aggregate media counts from all projects
    total_media_counts = {
        "video": 0,
        "audio": 0,
        "image": 0,
        "document": 0,
        "text": 0,
    }
    
    # Add creator-level media
    creator_media = _compute_media_counts(creator.get("media_groups", []))
    for media_type, count in creator_media.items():
        total_media_counts[media_type] += count
    
    # Add project-level media
    for project in creator.get("projects", []):
        project_media = _compute_media_counts(project.get("media_groups", []))
        for media_type, count in project_media.items():
            total_media_counts[media_type] += count
    
    return {
        "project_count": project_count,
        "media_counts": total_media_counts,
    }


def _build_project_overview_page(ctx: HtmlBuildContext, project_entries: List[Dict[str, Any]]):
    logger.info("Generating project overview page...")

    template = env.get_template("project_overview.html.j2")

    rendered = template.render(
        projects=project_entries,
        html_settings=ctx.html_settings,
        gallery_image_max_height=ctx.get_thumb_height(ThumbType.THUMB),
        ImageGalleryBuildingStrategy=ImageGalleryBuildingStrategy,
    )

    with open(ctx.projects_html_path, "w", encoding="utf-8") as f:
        f.write(rendered)


def _collect_tags_from_creator(creator: Dict) -> List[str]:
    tags = list(creator["tags"])
    for project in creator["projects"]:
        tags.extend(project["tags"])
    return tags


def _group_tags_by_category(tags: Iterable[str], fallback_category: str = "Other") -> Dict[str, List[str]]:
    """
    Groups tags by category. Tags with the format 'Category: Label' are grouped under 'Category'.
    Tags without a colon are grouped under the default 'Tag' category.

    Returns:
        A dictionary sorted by category name and tag name.
    """
    grouped: Dict[str, Set[str]] = defaultdict(set)

    for tag in tags:
        if ":" in tag:
            category, label = tag.split(":", 1)
            grouped[category.strip()].add(label.strip())
        else:
            grouped[fallback_category].add(tag.strip())

    return {category: sorted(grouped[category]) for category in sorted(grouped)}


def _build_tags_page(ctx: HtmlBuildContext, tags: List[str]):
    logger.info("Generating tags page...")

    template = env.get_template("tags.html.j2")

    output_html = template.render(
        html_settings=ctx.html_settings,
        tags=_group_tags_by_category(tags, ctx.fallback_tag_category),
    )

    with open(ctx.tags_html_path, "w", encoding="utf-8") as f:
        f.write(output_html)


def _create_symlink(input_dir: Path, rel_source_path: Path, target_dir: Path) -> Path:
    source_path = (input_dir / rel_source_path).resolve()
    target_path = target_dir / path_utils.build_unique_path(rel_source_path)

    if not source_path.exists():
        logger.warning(f"Cannot create symlink: source file not found: {source_path}")
    elif not target_path.exists():
        target_path.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(source_path, target_path)

    return target_path


def _sort_sections_by_type(sections: List[Dict], media_type_order: List[str]) -> List[Dict]:
    order_map = {t: i for i, t in enumerate(dict.fromkeys(media_type_order))}
    fallback_order = len(order_map)

    return sorted(sections, key=lambda s: order_map.get(s["type"], fallback_order))


def _get_section_titles(media_group: Dict, audio_section_title: str, image_section_title: str) -> Dict[str, str]:
    if not media_group["is_root"]:
        title = Path(media_group["rel_dir_path"]).name.title()
        audio_section_title = title
        image_section_title = title

    return {
        "audio_section_title": audio_section_title,
        "image_section_title": image_section_title,
    }


def _build_media_groups_context(ctx: HtmlBuildContext, media_groups: List) -> List[Dict[str, Any]]:
    media_groups_context = []

    for media_group in media_groups:
        rel_image_paths = _sample_images(media_group["images"], ctx.image_gallery_sample_max, ctx.image_gallery_sample_strategy)
        media_group_videos = media_group["videos"]
        rel_track_paths = media_group["tracks"]
        rel_document_paths = media_group["documents"]
        rel_text_paths = media_group["texts"]

        images = []
        for rel in rel_image_paths:
            thumbnail_context = _build_thumbnail_context(ctx, rel, ThumbType.GALLERY)
            images.append({
                "rel_thumbnail_path": thumbnail_context["rel_thumbnail_path"],
                "image_wrapper_width": thumbnail_context["image_wrapper_width"],
                "image_wrapper_height": thumbnail_context["image_wrapper_height"],
                "rel_path": path_utils.relative_path_from(_create_symlink(ctx.input_dir, Path(rel), ctx.symlinks_dir), ctx.output_dir).as_posix(),
                "caption": Path(rel).stem
            })

        videos = [{
            "rel_path": path_utils.relative_path_from(_create_symlink(ctx.input_dir, Path(v["file"]), ctx.symlinks_dir), ctx.output_dir).as_posix(),
            "title": Path(v["file"]).stem.title(),
            "rel_poster_path": path_utils.relative_path_from(_create_symlink(ctx.input_dir, Path(v["poster"]), ctx.symlinks_dir), ctx.output_dir).as_posix() if v["poster"] else ""
        } for v in media_group_videos]

        tracks = [{
            "rel_path": path_utils.relative_path_from(_create_symlink(ctx.input_dir, Path(rel), ctx.symlinks_dir), ctx.output_dir).as_posix(),
            "title": Path(rel).stem,
            "duration_seconds": audio_utils.get_audio_duration_seconds(ctx.input_dir / Path(rel))
        } for rel in rel_track_paths]

        documents = [{
            "rel_path": path_utils.relative_path_from(_create_symlink(ctx.input_dir, Path(rel), ctx.symlinks_dir), ctx.output_dir).as_posix(),
            "title": Path(rel).stem.title()
        } for rel in rel_document_paths]

        texts = [{
            "content": text_utils.markdown_to_html(text_utils.read_text(ctx.input_dir / Path(rel))),
            "title": Path(rel).stem.title()
        } for rel in rel_text_paths]

        section_titles = _get_section_titles(media_group, ctx.project_page_audio_section_base_title, ctx.project_page_image_section_base_title)

        sections = [
            {"type": MediaType.VIDEO.value, "videos": videos},
            {"type": MediaType.AUDIO.value, "tracks": tracks, "meta": {"total_duration_seconds": sum(t["duration_seconds"] for t in tracks)}},
            {"type": MediaType.IMAGE.value, "images": images},
            {"type": MediaType.DOCUMENT.value, "documents": documents},
            {"type": MediaType.TEXT.value, "texts": texts}
        ]

        media_groups_context.append({
            **section_titles,
            "sections": _sort_sections_by_type(sections, ctx.media_type_order)
        })

    return media_groups_context


def _calculate_age_at_release(creator: Dict, project: Dict) -> Optional[int]:
    if creator["type"] != CreatorType.PERSON:
        return None

    dob = creator["person"]["date_of_birth"]
    release = project["release_date"]

    if not dob or not release:
        return None

    return date_utils.calculate_age_from_strings(dob, release)


def _build_person_meta_entries(
    creator: Dict,
    visible: Set[CreatorField],
    project: Optional[Dict],
    field_order: Sequence[CreatorField],
) -> List[Dict[str, Any]]:
    person = creator["person"]
    entries = []

    field_builders = {
        CreatorField.CIVIL_NAME: lambda: _build_meta_entry("Civil Name", person["civil_name"]),
        CreatorField.ALIASES: lambda: _build_meta_entry("Aliases", creator["aliases"]),
        CreatorField.DATE_OF_BIRTH: lambda: _build_meta_entry("Born", date_utils.format_nice_date(person["date_of_birth"])),
        CreatorField.DATE_OF_DEATH: lambda: _build_meta_entry("Died", date_utils.format_nice_date(person["date_of_death"])),
        CreatorField.DEBUT_AGE: lambda: _build_meta_entry("Debut Age", date_utils.format_age(_calculate_debut_age(creator))),
    }

    for field in field_order:
        if field in visible and field in field_builders:
            entries.append(field_builders[field]())

    if project is not None and CreatorField.AGE_AT_TIME in visible:
        entries.append(_build_meta_entry("Age at Time", date_utils.format_age(_calculate_age_at_release(creator, project))))

    return entries


def _build_collaboration_meta_entries(
    creator: Dict,
    visible: Set[CreatorField],
    members_label: str,
    field_order: Sequence[CreatorField],
) -> List[Dict[str, Any]]:
    collab = creator["collaboration"]
    entries = []

    field_builders = {
        CreatorField.MEMBERS: lambda: _build_meta_entry(members_label, collab["members"], RenderMode.LIST),
        CreatorField.FOUNDING_DATE: lambda: _build_meta_entry("Founded", date_utils.format_nice_date(collab["founding_date"])),
        CreatorField.DISSOLUTION_DATE: lambda: _build_meta_entry("Dissolved", date_utils.format_nice_date(collab["dissolution_date"])),
    }

    for field in field_order:
        if field in visible and field in field_builders:
            entries.append(field_builders[field]())

    return entries


def _build_shared_creator_meta_entries(
    creator: Dict,
    visible: Set[CreatorField],
    field_order: Sequence[CreatorField],
) -> List[Dict[str, Any]]:
    field_builders = {
        CreatorField.NATIONALITY: lambda: _build_meta_entry("Nationality", creator["nationality"]),
        CreatorField.ACTIVE_SINCE: lambda: _build_meta_entry("Active Since", date_utils.format_nice_date(creator["active_since"])),
    }

    return [
        field_builders[field]()
        for field in field_order
        if field in visible and field in field_builders
    ]


def _build_creator_profile_meta_entries(
    creator: Dict,
    visible: Set[CreatorField],
    project: Optional[Dict] = None,
    link: Optional[str] = None,
    members_label: str = "Members",
    profile_fields: Optional[Sequence[CreatorField]] = None,
) -> List[Dict[str, Any]]:
    field_order = profile_fields or DEFAULT_CREATOR_FIELD_ORDER
    entries = [_build_meta_entry("Name", creator["name"], url=link)]

    if creator["type"] == CreatorType.PERSON:
        entries.extend(_build_person_meta_entries(creator, visible, project, field_order))
    else:
        entries.extend(_build_collaboration_meta_entries(creator, visible, members_label, field_order))

    entries.extend(_build_shared_creator_meta_entries(creator, visible, field_order))

    return _compact_meta_entries(entries)


def _collect_participant_entries(ctx: HtmlBuildContext, creator: Dict, project: Dict, get_creator) -> List[Dict[str, str]]:
    participants = []
    for name in creator["collaboration"]["members"]:
        participant = get_creator(name)
        if not participant:
            logger.warning(f"Missing creator reference: {name}")
            continue
        participants.append(_collect_creator_entries(ctx, participant, project))
    return participants


def _collect_creator_base_entries(ctx: HtmlBuildContext, creator: Dict) -> Dict[str, str]:
    thumb_path = _resolve_thumbnail_or_default(ctx, creator["portrait"], ThumbType.PORTRAIT)

    return {
        "name": creator["name"],
        "rel_html_path": (Path(ctx.html_dir.name) / _build_rel_creator_html_path(creator)).as_posix(),
        "rel_portrait_path": path_utils.relative_path_from(thumb_path, ctx.output_dir).as_posix(),
    }


def _collect_creator_entries(ctx: HtmlBuildContext, creator: Dict, project: Dict) -> Dict[str, Any]:
    entries = _collect_creator_base_entries(ctx, creator)
    visible = set(ctx.html_settings.get("creator_page_visible_fields", []))
    entries["profile_meta"] = _build_creator_profile_meta_entries(
        creator,
        visible,
        project=project,
        link=entries["rel_html_path"],
        members_label=ctx.html_settings["creator_page_members_title"],
    )
    return entries


def _collect_collaborator_entries(ctx: HtmlBuildContext, creator: Dict) -> Dict[str, Any]:
    entries = _collect_creator_base_entries(ctx, creator)
    visible = set(ctx.html_settings.get("creator_page_visible_fields", []))
    entries["profile_meta"] = _build_creator_profile_meta_entries(
        creator,
        visible,
        link=entries["rel_html_path"],
        members_label=ctx.html_settings["creator_page_members_title"],
    )
    return entries


def _collect_project_context(ctx: HtmlBuildContext, creator: Dict, project: Dict, get_creator, domain: Domain) -> Dict:
    visible = set(ctx.html_settings.get("project_page_visible_fields", []))
    thumb_path = _resolve_thumbnail_or_default(ctx, project["cover"], ThumbType.COVER)
    release_date = date_utils.format_nice_date(project["release_date"]) if ProjectField.RELEASE_DATE in visible else ""

    project_context = {
        "title": project["title"],
        "rel_thumbnail_path": path_utils.relative_path_from(thumb_path, ctx.output_dir).as_posix(),
        "thumbnail_orientation": image_utils.infer_image_orientation(thumb_path),
        "info_html": text_utils.markdown_to_html(project["info"]),
        "tag_map": _group_tags_by_category(project["tags"], ctx.fallback_tag_category),
        "meta": _build_project_meta_entries(domain, project, release_date),
        "media_groups": _build_media_groups_context(ctx, project["media_groups"]),
    }

    if creator["type"] == CreatorType.COLLABORATION:
        project_context["participants"] = _collect_participant_entries(ctx, creator, project, get_creator)
        project_context["collaboration"] = _collect_collaborator_entries(ctx, creator)
    else:
        project_context["creator"] = _collect_creator_entries(ctx, creator, project)

    return project_context


def _build_project_page(ctx: HtmlBuildContext, creator: Dict, project: Dict, get_creator, domain: Domain):
    logger.info(f"Building project page: {creator['name']} - {project['title']}")

    template = env.get_template("project.html.j2")

    output_html = template.render(
        html_settings=ctx.html_settings,
        project=_collect_project_context(ctx, creator, project, get_creator, domain),
        gallery_image_max_height=ctx.get_thumb_height(ThumbType.GALLERY),
        path_to_root=HTML_PATH_TO_ROOT,
        Orientation=Orientation,
    )

    page_path = ctx.html_dir / _build_rel_project_html_path(creator, project)
    page_path.parent.mkdir(parents=True, exist_ok=True)
    with open(page_path, "w", encoding="utf-8") as f:
        f.write(output_html)


def _get_collaboration_label(collab: Dict, creator_name: str) -> str:
    if creator_name in collab["collaboration"]["members"]:
        others = [n for n in collab["collaboration"]["members"] if n != creator_name]
        return " ".join(others)
    return collab["name"]


def _calculate_debut_age(creator: Dict) -> Optional[int]:
    dob = creator["person"]["date_of_birth"]
    active_since = creator["active_since"]

    if not dob:
        return None

    if active_since:
        return date_utils.calculate_age_from_strings(dob, active_since)

    dates = [p["release_date"] for p in creator["projects"] if date_utils.parse_date(p["release_date"])]
    if not dates:
        return None

    earliest = min(dates, key=lambda d: date_utils.parse_date(d))
    return date_utils.calculate_age_from_strings(dob, earliest)


def _build_project_entries(ctx: HtmlBuildContext, creator: Dict) -> List[Dict[str, Any]]:
    """
    Builds a list of dictionaries with metadata for each project of a creator,
    including title, html path, thumbnail path, and wrapper dimensions.
    """
    project_entries = []
    for project in sorted(creator["projects"], key=_sort_project):
        thumb = _build_thumbnail_context(ctx, project["cover"], ThumbType.GALLERY)
        project_entries.append({
            "title": project["title"],
            "rel_html_path": (Path(ctx.html_dir.name) / _build_rel_project_html_path(creator, project)).as_posix(),
            "rel_thumbnail_path": thumb["rel_thumbnail_path"],
            "image_wrapper_width": thumb["image_wrapper_width"],
            "image_wrapper_height": thumb["image_wrapper_height"],
            "media_counts": _compute_media_counts(project.get("media_groups", [])),
        })
    return project_entries


def _build_collaboration_entries(ctx: HtmlBuildContext, creator: Dict, get_creator) -> List[Dict[str, Any]]:
    """
    Builds a list of collaboration entries for a given creator.
    Each entry includes a label and a list of project entries.
    """
    collab_entries = []
    for collab_name in creator["collaborations"]:
        collab = get_creator(collab_name)
        if not collab:
            logger.warning(f"Missing creator reference: {collab_name}")
            continue

        collab_entries.append({
            "label": _get_collaboration_label(collab, creator["name"]),
            "projects": _build_project_entries(ctx, collab),
        })

    return collab_entries


def _collect_creator_context(ctx: HtmlBuildContext, creator: Dict, get_creator, creator_stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds the context dictionary for rendering a creator's page,
    including metadata, portrait, projects, collaborations, and tags.
    """
    visible = set(ctx.html_settings.get("creator_page_visible_fields", []))
    thumb_path = _resolve_thumbnail_or_default(ctx, creator["portrait"], ThumbType.PORTRAIT)

    context = {
        "type": creator["type"],
        "name": creator["name"],
        "rel_portrait_path": path_utils.relative_path_from(thumb_path, ctx.output_dir).as_posix(),
        "portrait_orientation": image_utils.infer_image_orientation(thumb_path),
        "profile_meta": _build_creator_profile_meta_entries(
            creator,
            visible,
            members_label=ctx.html_settings["creator_page_members_title"],
        ),
        "info_html": text_utils.markdown_to_html(creator["info"]),
        "tag_map": _group_tags_by_category(_collect_tags_from_creator(creator), ctx.fallback_tag_category),
        "projects": _build_project_entries(ctx, creator),
        "media_groups": _build_media_groups_context(ctx, creator["media_groups"]),
        "collaborations": _build_collaboration_entries(ctx, creator, get_creator),
        "creator_stats": creator_stats,
    }
    
    if creator["type"] == CreatorType.COLLABORATION:
        context["members"] = _collect_member_links(ctx, creator, get_creator)
    else:
        context["members"] = []

    return context


def _build_creator_page(ctx: HtmlBuildContext, creator: dict, get_creator, creator_stats: Dict[str, Any]):
    logger.info(f"Building creator page: {creator['name']}")

    template = env.get_template("creator.html.j2")

    output_html = template.render(
        html_settings=ctx.html_settings,
        creator=_collect_creator_context(ctx, creator, get_creator, creator_stats),
        member_thumb_max_height=ctx.get_thumb_height(ThumbType.THUMB),
        project_thumb_max_height=ctx.get_thumb_height(ThumbType.GALLERY),
        gallery_image_max_height=ctx.get_thumb_height(ThumbType.GALLERY),
        path_to_root=HTML_PATH_TO_ROOT,
        Orientation=Orientation,
        ImageGalleryBuildingStrategy=ImageGalleryBuildingStrategy,
    )

    page_path = ctx.html_dir / _build_rel_creator_html_path(creator)
    page_path.parent.mkdir(parents=True, exist_ok=True)
    with open(page_path, "w", encoding="utf-8") as f:
        f.write(output_html)


def _collect_member_links(ctx: HtmlBuildContext, creator: Dict, get_creator) -> List[Dict[str, str]]:
    """
    Builds a list of dictionaries representing links to member creators
    in a collaboration, including name, html path, and thumbnail path.
    """
    if creator["type"] != CreatorType.COLLABORATION:
        return []

    member_links = []

    for member_name in creator["collaboration"]["members"]:
        member = get_creator(member_name)
        if not member:
            logger.warning(f"Missing creator reference: {member_name}")
            continue

        thumb_path = _resolve_thumbnail_or_default(ctx, member["portrait"], ThumbType.THUMB)

        member_links.append({
            "name": member_name,
            "rel_html_path": (Path(ctx.html_dir.name) / _build_rel_creator_html_path(member)).as_posix(),
            "rel_thumbnail_path": path_utils.relative_path_from(thumb_path, ctx.output_dir).as_posix()
        })

    return member_links


def _build_creator_search_text(creator: Dict) -> str:
    """
    Builds a lowercase search text string from a creator's name, tags,
    project titles, media group labels, and project tags.
    """
    search_terms = [creator["name"]]
    search_terms.extend(creator["tags"])

    for project in creator["projects"]:
        search_terms.append(project["title"])
        search_terms.extend(project["tags"])

    return " ".join(search_terms).lower()


def _build_creator_overview_page(ctx: HtmlBuildContext, creator_entries: List[Dict[str, Any]]):
    logger.info("Generating overview page...")

    template = env.get_template("creator_overview.html.j2")

    output_html = template.render(
        html_settings=ctx.html_settings,
        creator_entries=creator_entries,
        gallery_image_max_height=ctx.get_thumb_height(ThumbType.THUMB),
        ImageGalleryBuildingStrategy=ImageGalleryBuildingStrategy,
    )

    with open(ctx.index_html_path, 'w', encoding='utf-8') as f:
        f.write(output_html)


def _validate_creator(creator: Dict, domain: Domain = Domain.CREATOR) -> Dict:
    try:
        return CreatorSchema.model_validate(creator, context={"domain": domain})
    except ValidationError as e:
        name = creator.get("name", "<unknown>")
        error_lines = [f"[{name}] {err['loc'][0]}: {err['msg']}" for err in e.errors()]
        formatted = "\n".join(error_lines)
        raise ValueError(f"Validation failed for creator '{name}':\n{formatted}")


def _load_validated_creator(json_path: Path, domain: Domain = Domain.CREATOR) -> Dict:
    raw_data = json_utils.load_json(json_path)
    return _validate_creator(raw_data, domain).model_dump(mode="json")


def _build_creator_metadata_index(input_dir: Path) -> Dict[str, Path]:
    creator_dirs: Dict[str, Path] = {}

    for creator_dir in sorted(input_dir.iterdir()):
        if not creator_dir.is_dir():
            continue

        json_path = creator_dir / CR4TE_JSON_FILE_NAME
        if not json_path.exists():
            continue

        try:
            raw_data = json_utils.load_json(json_path)
        except Exception as e:
            logger.warning(f"Unable to read creator JSON at {json_path}: {e}")
            continue

        name = raw_data.get("name")
        if not isinstance(name, str) or not name.strip():
            logger.warning(f"Missing or invalid creator name in {json_path}")
            continue

        if name in creator_dirs:
            logger.warning(f"Duplicate creator name: {name} in {json_path}; keeping first")
            continue

        creator_dirs[name] = creator_dir

    return creator_dirs


def _get_creator_loader(creator_dirs: Dict[str, Path], domain: Domain) -> Tuple[Any, Dict[str, Dict[str, Any]]]:
    cache: Dict[str, Dict[str, Any]] = {}

    def loader(name: str) -> Optional[Dict[str, Any]]:
        if name in cache:
            return cache[name]

        creator_dir = creator_dirs.get(name)
        if not creator_dir:
            return None

        json_path = creator_dir / CR4TE_JSON_FILE_NAME
        if not json_path.exists():
            return None

        creator = _load_validated_creator(json_path, domain)
        cache[name] = creator
        return creator

    return loader, cache


def _build_creator_summary_entry(ctx: HtmlBuildContext, creator: Dict[str, Any], creator_stats: Dict[str, Any]) -> Dict[str, Any]:
    thumb = _build_thumbnail_context(ctx, creator["portrait"], ThumbType.THUMB)
    return {
        "name": creator["name"],
        "rel_html_path": (Path(ctx.html_dir.name) / _build_rel_creator_html_path(creator)).as_posix(),
        "search_text": _build_creator_search_text(creator),
        "rel_thumbnail_path": thumb["rel_thumbnail_path"],
        "image_wrapper_width": thumb["image_wrapper_width"],
        "image_wrapper_height": thumb["image_wrapper_height"],
        "project_count": creator_stats["project_count"],
        "media_counts": creator_stats["media_counts"],
    }


def _build_project_summary_entry(ctx: HtmlBuildContext, creator: Dict[str, Any], project: Dict[str, Any]) -> Dict[str, Any]:
    thumb = _build_thumbnail_context(ctx, project["cover"], ThumbType.GALLERY)
    return {
        "title": project["title"],
        "rel_html_path": (Path(ctx.html_dir.name) / _build_rel_project_html_path(creator, project)).as_posix(),
        "rel_thumbnail_path": thumb["rel_thumbnail_path"],
        "creator_name": creator["name"],
        "search_text": _build_project_search_text(project, creator["name"]),
        "media_counts": _compute_media_counts(project.get("media_groups", [])),
    }

# TODO: Take aspect ratio and name from html_settings
def _prepare_static_assets(ctx: HtmlBuildContext) -> None:
    shutil.copytree(CR4TE_CSS_DIR, ctx.css_dir, dirs_exist_ok=True)
    shutil.copytree(CR4TE_JS_DIR, ctx.js_dir, dirs_exist_ok=True)

    ctx.defaults_dir.mkdir(parents=True, exist_ok=True)
    th = ctx.get_thumb_height(ThumbType.THUMB)
    image_utils.create_centered_text_image(int(th * 3 / 4), th, "Thumb", ctx.get_default_thumb_path(ThumbType.THUMB))

    ph = ctx.get_thumb_height(ThumbType.PORTRAIT)
    image_utils.create_centered_text_image(int(ph * 3 / 4), ph, "Portrait", ctx.get_default_thumb_path(ThumbType.PORTRAIT))

    ch = ctx.get_thumb_height(ThumbType.COVER)
    image_utils.create_centered_text_image(int(ch * 4 / 3), ch, "Cover", ctx.get_default_thumb_path(ThumbType.COVER))


def _prepare_output_dirs(ctx: HtmlBuildContext) -> None:
    ctx.output_dir.mkdir(parents=True, exist_ok=True)
    ctx.html_dir.mkdir(parents=True, exist_ok=True)
    ctx.thumbs_dir.mkdir(parents=True, exist_ok=True)


def build_html_pages(input_dir: Path, output_dir: Path, html_settings: Dict, domain: Domain = Domain.CREATOR) -> Path:
    ctx = HtmlBuildContext(input_dir, output_dir, html_settings)

    _prepare_output_dirs(ctx)
    _prepare_static_assets(ctx)

    creator_dirs = _build_creator_metadata_index(ctx.input_dir)
    get_creator, cache = _get_creator_loader(creator_dirs, domain)

    creator_entries: List[Dict[str, Any]] = []
    project_entries: List[Dict[str, Any]] = []
    all_tags: List[str] = []
    failures: List[tuple[str, Exception]] = []

    for creator_name in sorted(creator_dirs):
        creator_dir = creator_dirs[creator_name]
        json_path = creator_dir / CR4TE_JSON_FILE_NAME

        try:
            creator = _load_validated_creator(json_path, domain)
            cache[creator_name] = creator

            creator_stats = _compute_creator_stats(creator)
            _build_creator_page(ctx, creator, get_creator, creator_stats)

            for project in sorted(creator["projects"], key=_sort_project):
                _build_project_page(ctx, creator, project, get_creator, domain)
                project_entries.append(_build_project_summary_entry(ctx, creator, project))

            creator_entries.append(_build_creator_summary_entry(ctx, creator, creator_stats))
            all_tags.extend(_collect_tags_from_creator(creator))

        except Exception as e:
            logger.exception(f"{creator_dir.name}: failed to process")
            failures.append((creator_dir.name, e))
            continue

    creator_entries.sort(key=lambda e: e["name"].lower())
    project_entries.sort(key=lambda e: (e["title"].lower(), e["creator_name"].lower()))

    _build_creator_overview_page(ctx, creator_entries)
    _build_project_overview_page(ctx, project_entries)
    _build_tags_page(ctx, all_tags)

    if failures:
        logger.error(
            "HTML build completed with %s succeeded creator(s) and %s failed creator(s).",
            len(creator_entries),
            len(failures),
        )
        raise ValueError(format_build_failures("HTML build", failures))

    return ctx.index_html_path


def clear_output_folder(output_dir: Path, clear_thumbnails: bool):
    for item in output_dir.iterdir():
        if clear_thumbnails or item.name != THUMBNAILS_DIRNAME:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
