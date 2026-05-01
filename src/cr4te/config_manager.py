import logging
import copy
from pathlib import Path
from typing import Dict, Optional

from pydantic import ValidationError

from .utils.json_utils import load_json
from .validators.config_schema import AppConfig
from .enums.visible_fields import CreatorField, ProjectField
from .enums.image_sample_strategy import ImageSampleStrategy
from .enums.portrait_strategy import PortraitStrategy
from .enums.media_type import MediaType
from .enums.domain import Domain
from .enums.image_gallery_building_strategy import ImageGalleryBuildingStrategy

logger = logging.getLogger(__name__)

__all__ = ["load_config", "apply_cli_overrides"]

# === Default internal config ===
DEFAULT_CONFIG = {
    "html_settings": {
        "nav_creators_label": "Creators",
        "nav_projects_label": "Projects",
        "nav_tags_label": "Tags",
        
        "fallback_tag_category": "Other",
        
        "creator_overview_page_title": "Creators",
        "creator_overview_page_search_placeholder": "Search creators, projects, tags...",
        
        "project_overview_page_title": "Projects",
        "project_overview_page_search_placeholder": "Search projects, tags...",
        
        "creator_page_profile_title": "Profile",
        "creator_page_about_title": "About",
        "creator_page_tags_title": "Tags",
        "creator_page_members_title": "Members",
        "creator_page_projects_title": "Projects",
        "creator_page_collabs_title_prefix": "With",
              
        "project_page_overview_title": "Overview",
        "project_page_description_title": "Description",
        "project_page_tags_title": "Tags",
        "project_page_audio_section_base_title": "Audio",
        "project_page_image_section_base_title": "Images",
        
        "tags_page_title": "Tags",
        
        "image_gallery_sample_max": 20,
        "image_gallery_sample_strategy": ImageSampleStrategy.SPREAD,
        
        "media_type_order": [MediaType.VIDEO, MediaType.AUDIO, MediaType.IMAGE, MediaType.TEXT, MediaType.DOCUMENT],
        
        "creator_gallery_building_strategy": ImageGalleryBuildingStrategy.ASPECT,
        "creator_gallery_aspect_ratio": "2/3",
        
        "project_gallery_building_strategy": ImageGalleryBuildingStrategy.ASPECT,
        "project_gallery_aspect_ratio": "3/2",
        
        "creator_overview_page_creator_gallery_page_size": 100,
        
        "project_overview_page_project_gallery_page_size": 100,
        
        "creator_page_visible_fields": [f for f in CreatorField],
        "creator_page_image_gallery_page_size" : 15,

        "project_page_visible_fields": [f for f in ProjectField],
        "project_page_image_gallery_page_size" : 15,
        
        "hide_portraits": False,
    },
    "media_rules": {   
        "max_search_depth": 5,
        
        "global_exclude_prefix": "_",
        
        "metadata_folder_name": "meta",
        "collaboration_separators": ["&", ","],
        
        "portrait_basename": "portrait",
        "cover_basename": "cover",
        
        "auto_find_portraits": False,
    }
}

def _validate_config(config: Dict) -> None:
    try:
        AppConfig(**config)
    except ValidationError as e:
        error_lines = [f"[AppConfig] {' > '.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
        formatted = "\n".join(error_lines)
        raise ValueError(f"Validation failed for config:\n{formatted}")      
    
def load_config(user_config_path: Path = None) -> Dict:
    config = copy.deepcopy(DEFAULT_CONFIG)
 
    if user_config_path:
        try:
            user_config = load_json(user_config_path)
            config["html_settings"].update(user_config.get("html_settings", {}))
            config["media_rules"].update(user_config.get("media_rules", {}))
            logger.info(f"Loaded configuration from {user_config_path}")
        except Exception as e:
            logger.warning(
                f"Could not load config file {user_config_path}: {e}\n"
                "Proceeding with default internal configuration."
            )

    _validate_config(config)

    return config
       
def apply_cli_overrides(config: Dict, image_sample_strategy: Optional[ImageSampleStrategy] = None, portrait_strategy: Optional[PortraitStrategy] = None, domain: Optional[Domain] = None) -> Dict:
    if domain is not None:
        preset = _get_preset(domain)
        config["html_settings"].update(preset["html_settings"])
        config["media_rules"].update(preset["media_rules"])

    if image_sample_strategy is not None:
        config["html_settings"]["image_gallery_sample_strategy"] = image_sample_strategy
      
    match portrait_strategy:
        case PortraitStrategy.NONE:
            config["media_rules"]["auto_find_portraits"] = False
            config["html_settings"]["hide_portraits"] = True
        case PortraitStrategy.NAMED:
            config["media_rules"]["auto_find_portraits"] = False
            config["html_settings"]["hide_portraits"] = False
        case PortraitStrategy.AUTO:
            config["media_rules"]["auto_find_portraits"] = True
            config["html_settings"]["hide_portraits"] = False
    
    _validate_config(config)

    return config
 
def _get_preset(domain: Domain) -> Dict:
    """
    Returns all config overrides for the selected domain, 
    including labels, media ordering, and gallery settings.
    """
    match domain:
        case Domain.CREATOR:
            return {
                "html_settings": {},
                "media_rules": {},
            }
        case Domain.FILM:
            return {
                "html_settings": {
                    "nav_creators_label": "Directors",
                    "nav_projects_label": "Movies",
                    "creator_overview_page_title": "Directors",
                    "creator_overview_page_search_placeholder": "Search directors, movies, tags...",
                    "project_overview_page_title": "Movies",
                    "project_overview_page_search_placeholder": "Search movies, tags...",
                    "creator_page_projects_title": "Movies",
                    "project_page_audio_section_base_title": "Soundtrack",
                    "project_gallery_aspect_ratio": "2/3",
                 },
               "media_rules": {},
            }
        case Domain.MUSIC:
            return {
                "html_settings": {
                    "nav_creators_label": "Musicians",
                    "nav_projects_label": "Albums",
                    "creator_overview_page_title": "Musicians",
                    "creator_overview_page_search_placeholder": "Search musicians, albums, tags...",
                    "project_overview_page_title": "Albums",
                    "project_overview_page_search_placeholder": "Search albums, tags...",
                    "creator_page_projects_title": "Albums",
                    "project_page_audio_section_base_title": "Tracks",
                    "media_type_order": [MediaType.AUDIO, MediaType.IMAGE, MediaType.TEXT, MediaType.DOCUMENT, MediaType.VIDEO],
                    "project_gallery_aspect_ratio": "1/1",
                },
               "media_rules": {},
            }
        case Domain.ART:
            return {
                "html_settings": {
                    "nav_creators_label": "Artists",
                    "nav_projects_label": "Works",
                    "creator_overview_page_title": "Artists",
                    "creator_overview_page_search_placeholder": "Search artists, works, tags...",
                    "project_overview_page_title": "Works",
                    "project_overview_page_search_placeholder": "Search works, tags...",
                    "creator_page_projects_title": "Works",
                    "media_type_order": [MediaType.AUDIO, MediaType.IMAGE, MediaType.TEXT, MediaType.DOCUMENT, MediaType.VIDEO],
                    "project_gallery_aspect_ratio": "1/1",
                },
               "media_rules": {},
            }
        case Domain.BOOK:
            return {
                "html_settings": {
                    "nav_creators_label": "Author",
                    "nav_projects_label": "Books",
                    "creator_overview_page_title": "Author",
                    "creator_overview_page_search_placeholder": "Search author, books, tags...",
                    "project_overview_page_title": "Books",
                    "project_overview_page_search_placeholder": "Search books, tags...",
                    "creator_page_projects_title": "Books",
                    "project_page_audio_section_base_title": "Audio",
                    "media_type_order": [MediaType.DOCUMENT, MediaType.AUDIO, MediaType.IMAGE, MediaType.TEXT, MediaType.VIDEO],
                    "project_gallery_aspect_ratio": "1000/1414",
                },
               "media_rules": {},
            }
        case Domain.MODEL:
            return {
                "html_settings": {
                    "nav_creators_label": "Models",
                    "nav_projects_label": "Scenes",
                    "creator_overview_page_title": "Models",
                    "creator_overview_page_search_placeholder": "Search models, scenes, tags...",
                    "project_overview_page_title": "Scenes",
                    "project_overview_page_search_placeholder": "Search scenes, tags...",
                    "creator_page_projects_title": "Scenes",
                    "creator_page_collabs_title_prefix": "Scenes with",
                    "creator_page_members_title": "Featuring",
                    "media_type_order": [MediaType.VIDEO, MediaType.IMAGE, MediaType.TEXT, MediaType.DOCUMENT, MediaType.AUDIO],
                },
               "media_rules": {},
            }
        case _:
            raise ValueError(f"Unknown domain: {domain}")

