from typing import Dict, List
import re

from pydantic import BaseModel, ConfigDict, Field, conint, validator

from ..enums.image_sample_strategy import ImageSampleStrategy
from ..enums.image_gallery_building_strategy import ImageGalleryBuildingStrategy
from ..enums.media_type import MediaType
from ..enums.visible_fields import CreatorField, ProjectField

# Site schema
class SectionLabels(BaseModel):
    profile: str
    about: str
    members: str
    collabs_title_prefix: str
    overview: str
    description: str
    audio: str
    images: str


class FallbackImageLabels(BaseModel):
    thumb: str
    portrait: str
    cover: str


class MetadataLabels(BaseModel):
    __pydantic_extra__: Dict[str, str] = Field(init=False)

    model_config = ConfigDict(extra="allow")

    title: str
    release_date: str
    name: str
    civil_name: str
    aliases: str
    born: str
    died: str
    debut_age: str
    age_at_time: str
    founded: str
    dissolved: str
    nationality: str
    active_since: str


class SiteLabels(BaseModel):
    creators: str
    projects: str
    tags: str
    themes: str
    search: str
    fallback_tag_category: str
    sections: SectionLabels
    fallback_images: FallbackImageLabels
    metadata: MetadataLabels


class GalleryDisplay(BaseModel):
    building_strategy: ImageGalleryBuildingStrategy
    aspect_ratio: str


class PaginationDisplay(BaseModel):
    creator_overview_gallery_page_size: conint(ge=0)
    project_overview_gallery_page_size: conint(ge=0)
    creator_page_image_gallery_page_size: conint(ge=0)
    project_page_image_gallery_page_size: conint(ge=0)


class VisibleFieldsDisplay(BaseModel):
    creator_page: List[CreatorField]
    project_page: List[ProjectField]


class SiteDisplay(BaseModel):
    image_gallery_sample_max: conint(ge=0)
    image_gallery_sample_strategy: ImageSampleStrategy
    media_type_order: List[MediaType]
    hide_portraits: bool
    creator_gallery: GalleryDisplay
    project_gallery: GalleryDisplay
    pagination: PaginationDisplay
    visible_fields: VisibleFieldsDisplay


class SiteConfig(BaseModel):
    labels: SiteLabels
    display: SiteDisplay

    @validator('display')
    def validate_gallery_aspect_ratios(cls, v):
        for aspect_ratio in (v.creator_gallery.aspect_ratio, v.project_gallery.aspect_ratio):
            cls.validate_aspect_ratio_colon_format(aspect_ratio)
        return v

    @classmethod
    def validate_aspect_ratio_colon_format(cls, v):
        match = re.match(r'^(\d+)/(\d+)$', v.strip())
        if not match:
            raise ValueError("Aspect ratio must be in the format 'w/h' (e.g., '4/3')")
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
    site: SiteConfig
    media_rules: MediaRules

