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
    "site": {
        "labels": {
            "creators": "Creators",
            "projects": "Projects",
            "tags": "Tags",
            "themes": "Themes",
            "search": "Search ",
            "fallback_tag_category": "Other",
            "sections": {
                "profile": "Profile",
                "about": "About",
                "members": "Members",
                "collabs_title_prefix": "with",
                "overview": "Overview",
                "description": "Description",
                "audio": "Audio",
                "images": "Images",
            },
            "fallback_images": {
                "thumb": "Thumb",
                "portrait": "Portrait",
                "cover": "Cover",
            },
            "metadata": {
                "title": "Title",
                "release_date": "Release Date",
                "name": "Name",
                "civil_name": "Civil Name",
                "aliases": "Aliases",
                "born": "Born",
                "died": "Died",
                "debut_age": "Debut Age",
                "age_at_time": "Age at Time",
                "founded": "Founded",
                "dissolved": "Dissolved",
                "nationality": "Nationality",
                "active_since": "Active Since",
                "makeup_artists": "Makeup Artists",
                "isbns": "ISBNs",
                "citations": "Citations",
                "cover_artists": "Cover Artists",
                "actors": "Actors",
                "score_composers": "Score Composers",
                "visual_effects": "Visual Effects",
                "costume_designers": "Costume Designers",
            },
        },
        "display": {
            "image_gallery_sample_max": 20,
            "image_gallery_sample_strategy": ImageSampleStrategy.SPREAD,
            "media_type_order": [MediaType.VIDEO, MediaType.AUDIO, MediaType.IMAGE, MediaType.TEXT, MediaType.DOCUMENT],
            "hide_portraits": False,
            "creator_gallery": {
                "building_strategy": ImageGalleryBuildingStrategy.ASPECT,
                "aspect_ratio": "2/3",
            },
            "project_gallery": {
                "building_strategy": ImageGalleryBuildingStrategy.ASPECT,
                "aspect_ratio": "3/2",
            },
            "pagination": {
                "creator_overview_gallery_page_size": 100,
                "project_overview_gallery_page_size": 100,
                "creator_page_image_gallery_page_size": 15,
                "project_page_image_gallery_page_size": 15,
            },
            "visible_fields": {
                "creator_page": [f for f in CreatorField],
                "project_page": [f for f in ProjectField],
            },
        },
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


def _deep_update(base: Dict, overrides: Dict) -> Dict:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _validate_config(config: Dict) -> Dict:
    try:
        return AppConfig(**config).model_dump(mode="python")
    except ValidationError as e:
        error_lines = [f"[AppConfig] {' > '.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
        formatted = "\n".join(error_lines)
        raise ValueError(f"Validation failed for config:\n{formatted}")      
    
def load_config(user_config_path: Path = None) -> Dict:
    config = copy.deepcopy(DEFAULT_CONFIG)
 
    if user_config_path:
        try:
            user_config = load_json(user_config_path)
            _deep_update(config["site"], user_config.get("site", {}))
            _deep_update(config["media_rules"], user_config.get("media_rules", {}))
            logger.info(f"Loaded configuration from {user_config_path}")
        except Exception as e:
            logger.warning(
                f"Could not load config file {user_config_path}: {e}\n"
                "Proceeding with default internal configuration."
            )

    return _validate_config(config)
       
def apply_cli_overrides(config: Dict, image_sample_strategy: Optional[ImageSampleStrategy] = None, portrait_strategy: Optional[PortraitStrategy] = None, domain: Optional[Domain] = None) -> Dict:
    config = copy.deepcopy(config)

    if domain is not None:
        preset = _get_preset(domain)
        _deep_update(config["site"], preset["site"])
        _deep_update(config["media_rules"], preset["media_rules"])

    if image_sample_strategy is not None:
        config["site"]["display"]["image_gallery_sample_strategy"] = image_sample_strategy
      
    match portrait_strategy:
        case PortraitStrategy.NONE:
            config["media_rules"]["auto_find_portraits"] = False
            config["site"]["display"]["hide_portraits"] = True
        case PortraitStrategy.NAMED:
            config["media_rules"]["auto_find_portraits"] = False
            config["site"]["display"]["hide_portraits"] = False
        case PortraitStrategy.AUTO:
            config["media_rules"]["auto_find_portraits"] = True
            config["site"]["display"]["hide_portraits"] = False
    
    return _validate_config(config)
 
def _get_preset(domain: Domain) -> Dict:
    """
    Returns all config overrides for the selected domain, 
    including labels, media ordering, and gallery settings.
    """
    match domain:
        case Domain.CREATOR:
            return {
                "site": {},
                "media_rules": {},
            }
        case Domain.FILM:
            return {
                "site": {
                    "labels": {
                        "creators": "Directors",
                        "projects": "Movies",
                        "sections": {
                            "audio": "Soundtrack",
                        },
                        "metadata": {
                            "actors": "Cast",
                        },
                    },
                    "display": {
                        "project_gallery": {
                            "aspect_ratio": "2/3",
                        },
                    },
                },
                "media_rules": {},
            }
        case Domain.MUSIC:
            return {
                "site": {
                    "labels": {
                        "creators": "Musicians",
                        "projects": "Albums",
                        "sections": {
                            "audio": "Tracks",
                        },
                    },
                    "display": {
                        "media_type_order": [MediaType.AUDIO, MediaType.VIDEO, MediaType.IMAGE, MediaType.TEXT, MediaType.DOCUMENT],
                        "project_gallery": {
                            "aspect_ratio": "1/1",
                        },
                    },
                },
                "media_rules": {},
            }
        case Domain.ART:
            return {
                "site": {
                    "labels": {
                        "creators": "Artists",
                        "projects": "Works",
                    },
                    "display": {
                        "media_type_order": [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO, MediaType.DOCUMENT, MediaType.TEXT],
                        "project_gallery": {
                            "aspect_ratio": "1/1",
                        },
                    },
                },
                "media_rules": {},
            }
        case Domain.BOOK:
            return {
                "site": {
                    "labels": {
                        "creators": "Authors",
                        "projects": "Books",
                        "sections": {
                            "audio": "Audio",
                        },
                    },
                    "display": {
                        "media_type_order": [MediaType.DOCUMENT, MediaType.AUDIO, MediaType.IMAGE, MediaType.VIDEO, MediaType.TEXT],
                        "project_gallery": {
                            "aspect_ratio": "1000/1414",
                        },
                    },
                },
                "media_rules": {},
            }
        case Domain.MODEL:
            return {
                "site": {
                    "labels": {
                        "creators": "Models",
                        "projects": "Scenes",
                        "sections": {
                            "collabs_title_prefix": "with",
                            "members": "Featuring",
                        },
                    },
                    "display": {
                        "media_type_order": [MediaType.VIDEO, MediaType.IMAGE, MediaType.TEXT, MediaType.DOCUMENT, MediaType.AUDIO],
                    },
                },
                "media_rules": {},
            }
        case _:
            raise ValueError(f"Unknown domain: {domain}")

