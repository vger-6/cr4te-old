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
        "creators_label": "Creators",
        "projects_label": "Projects",
        "tags_label": "Tags",
        "search_label": "Search ",
        
        "fallback_tag_category": "Other",
        
        "creator_page_profile_title": "Profile",
        "creator_page_about_title": "About",
        "creator_page_members_title": "Members",
        "creator_page_collabs_title_prefix": "With",
              
        "project_page_overview_title": "Overview",
        "project_page_description_title": "Description",
        "project_page_audio_section_base_title": "Audio",
        "project_page_image_section_base_title": "Images",
        
        "image_gallery_sample_max": 20,
        "image_gallery_sample_strategy": ImageSampleStrategy.SPREAD,
        
        "media_type_order": [MediaType.VIDEO, MediaType.AUDIO, MediaType.IMAGE, MediaType.TEXT, MediaType.DOCUMENT],
        
        "creator_gallery_building_strategy": ImageGalleryBuildingStrategy.ASPECT,
        "creator_gallery_aspect_ratio": "2/3",
        
        "project_gallery_building_strategy": ImageGalleryBuildingStrategy.ASPECT,
        "project_gallery_aspect_ratio": "3/2",
        
        "creator_overview_gallery_page_size": 100,
        
        "project_overview_gallery_page_size": 100,
        
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
                    "creators_label": "Directors",
                    "projects_label": "Movies",
                    "project_page_audio_section_base_title": "Soundtrack",
                    "project_gallery_aspect_ratio": "2/3",
                 },
               "media_rules": {},
            }
        case Domain.MUSIC:
            return {
                "html_settings": {
                    "creators_label": "Musicians",
                    "projects_label": "Albums",
                    "project_page_audio_section_base_title": "Tracks",
                    "media_type_order": [MediaType.AUDIO, MediaType.VIDEO, MediaType.IMAGE, MediaType.TEXT, MediaType.DOCUMENT],
                    "project_gallery_aspect_ratio": "1/1",
                },
               "media_rules": {},
            }
        case Domain.ART:
            return {
                "html_settings": {
                    "creators_label": "Artists",
                    "projects_label": "Works",
                    "media_type_order": [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO, MediaType.DOCUMENT, MediaType.TEXT],
                    "project_gallery_aspect_ratio": "1/1",
                },
               "media_rules": {},
            }
        case Domain.BOOK:
            return {
                "html_settings": {
                    "creators_label": "Authors",
                    "projects_label": "Books",
                    "project_page_audio_section_base_title": "Audio",
                    "media_type_order": [MediaType.DOCUMENT, MediaType.AUDIO, MediaType.IMAGE, MediaType.VIDEO, MediaType.TEXT],
                    "project_gallery_aspect_ratio": "1000/1414",
                },
               "media_rules": {},
            }
        case Domain.MODEL:
            return {
                "html_settings": {
                    "creators_label": "Models",
                    "projects_label": "Scenes",
                    "creator_page_collabs_title_prefix": "Scenes with",
                    "creator_page_members_title": "Featuring",
                    "media_type_order": [MediaType.VIDEO, MediaType.IMAGE, MediaType.TEXT, MediaType.DOCUMENT, MediaType.AUDIO],
                },
               "media_rules": {},
            }
        case _:
            raise ValueError(f"Unknown domain: {domain}")

