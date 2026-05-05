from typing import List
import re

from pydantic import BaseModel, conint, validator

from ..enums.image_sample_strategy import ImageSampleStrategy
from ..enums.image_gallery_building_strategy import ImageGalleryBuildingStrategy
from ..enums.media_type import MediaType
from ..enums.visible_fields import CreatorField, ProjectField

# HTML settings schema
class HtmlSettings(BaseModel):
    creators_label: str
    projects_label: str
    tags_label: str
    search_label: str

    creator_page_profile_title: str
    creator_page_about_title: str
    creator_page_collabs_title_prefix: str

    project_page_overview_title: str
    project_page_description_title: str
    default_audio_section_title: str
    default_image_section_title: str
    
    image_gallery_sample_max: conint(ge=0)
    image_gallery_sample_strategy: ImageSampleStrategy
    
    media_type_order: List[MediaType]
    
    creator_gallery_building_strategy: ImageGalleryBuildingStrategy
    creator_gallery_aspect_ratio: str
    
    project_gallery_building_strategy: ImageGalleryBuildingStrategy
    project_gallery_aspect_ratio: str
    
    creator_overview_gallery_page_size: conint(ge=0)
    
    project_overview_gallery_page_size: conint(ge=0)
    
    creator_page_visible_fields: List[CreatorField]
    creator_page_image_gallery_page_size: conint(ge=0)
    
    project_page_visible_fields: List[ProjectField]
    project_page_image_gallery_page_size: conint(ge=0)
    
    hide_portraits: bool
    
    @validator('project_gallery_aspect_ratio', 'creator_gallery_aspect_ratio')
    def validate_aspect_ratio_colon_format(cls, v):
        match = re.match(r'^(\d+)/(\d+)$', v.strip())
        if not match:
            raise ValueError("Aspect ratio must be in the format 'w:h' (e.g., '4/3')")
        w, h = map(int, match.groups())
        if w <= 0 or h <= 0:
            raise ValueError("Aspect ratio values must be greater than zero")
        return v.strip()

# Media rules schema
class MediaRules(BaseModel):
    max_search_depth: conint(ge=0)
    global_exclude_prefix: str
    metadata_folder_name: str
    collaboration_separators: List[str]
    portrait_basename: str
    cover_basename: str
    auto_find_portraits: bool

# Top-level config schema
class AppConfig(BaseModel):
    html_settings: HtmlSettings
    media_rules: MediaRules

