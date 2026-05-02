from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from ..enums.thumb_type import ThumbType
from ..enums.visible_fields import CreatorField, ProjectField
from ..enums.image_sample_strategy import ImageSampleStrategy
from ..enums.image_gallery_building_strategy import ImageGalleryBuildingStrategy
from ..enums.media_type import MediaType
from ..context.base_context import BaseContext
from ..constants import (
    CR4TE_PACKAGE_DIR,
    CR4TE_DEFAULTS_DIR,
    CR4TE_CSS_DIR, 
    CR4TE_JS_DIR,
)

# === Output folder names ===
THUMBNAILS_DIRNAME = "thumbnails"

@dataclass
class SectionLabels:
    raw: Dict

    @property
    def profile(self) -> str:
        return self.raw["profile"]

    @property
    def about(self) -> str:
        return self.raw["about"]

    @property
    def members(self) -> str:
        return self.raw["members"]

    @property
    def collabs_title_prefix(self) -> str:
        return self.raw["collabs_title_prefix"]

    @property
    def overview(self) -> str:
        return self.raw["overview"]

    @property
    def description(self) -> str:
        return self.raw["description"]

    @property
    def audio(self) -> str:
        return self.raw["audio"]

    @property
    def images(self) -> str:
        return self.raw["images"]


@dataclass
class FallbackImageLabels:
    raw: Dict

    @property
    def thumb(self) -> str:
        return self.raw["thumb"]

    @property
    def portrait(self) -> str:
        return self.raw["portrait"]

    @property
    def cover(self) -> str:
        return self.raw["cover"]


@dataclass
class SiteLabels:
    raw: Dict

    @property
    def creators(self) -> str:
        return self.raw["creators"]

    @property
    def projects(self) -> str:
        return self.raw["projects"]

    @property
    def tags(self) -> str:
        return self.raw["tags"]

    @property
    def themes(self) -> str:
        return self.raw["themes"]

    @property
    def search(self) -> str:
        return self.raw["search"]

    @property
    def fallback_tag_category(self) -> str:
        return self.raw["fallback_tag_category"]

    @property
    def sections(self) -> SectionLabels:
        return SectionLabels(self.raw["sections"])

    @property
    def fallback_images(self) -> FallbackImageLabels:
        return FallbackImageLabels(self.raw["fallback_images"])

    @property
    def metadata(self) -> Dict:
        return self.raw["metadata"]


@dataclass
class GalleryDisplay:
    raw: Dict

    @property
    def building_strategy(self) -> ImageGalleryBuildingStrategy:
        return self.raw["building_strategy"]

    @property
    def aspect_ratio(self) -> str:
        return self.raw["aspect_ratio"]


@dataclass
class PaginationDisplay:
    raw: Dict

    @property
    def creator_overview_gallery_page_size(self) -> int:
        return self.raw["creator_overview_gallery_page_size"]

    @property
    def project_overview_gallery_page_size(self) -> int:
        return self.raw["project_overview_gallery_page_size"]

    @property
    def creator_page_image_gallery_page_size(self) -> int:
        return self.raw["creator_page_image_gallery_page_size"]

    @property
    def project_page_image_gallery_page_size(self) -> int:
        return self.raw["project_page_image_gallery_page_size"]


@dataclass
class VisibleFieldsDisplay:
    raw: Dict

    @property
    def creator_page(self) -> List[CreatorField]:
        return self.raw["creator_page"]

    @property
    def project_page(self) -> List[ProjectField]:
        return self.raw["project_page"]


@dataclass
class SiteDisplay:
    raw: Dict

    @property
    def image_gallery_sample_max(self) -> int:
        return self.raw["image_gallery_sample_max"]

    @property
    def image_gallery_sample_strategy(self) -> ImageSampleStrategy:
        return self.raw["image_gallery_sample_strategy"]

    @property
    def media_type_order(self) -> List[MediaType]:
        return self.raw["media_type_order"]

    @property
    def hide_portraits(self) -> bool:
        return self.raw["hide_portraits"]

    @property
    def creator_gallery(self) -> GalleryDisplay:
        return GalleryDisplay(self.raw["creator_gallery"])

    @property
    def project_gallery(self) -> GalleryDisplay:
        return GalleryDisplay(self.raw["project_gallery"])

    @property
    def pagination(self) -> PaginationDisplay:
        return PaginationDisplay(self.raw["pagination"])

    @property
    def visible_fields(self) -> VisibleFieldsDisplay:
        return VisibleFieldsDisplay(self.raw["visible_fields"])


@dataclass
class HtmlBuildContext(BaseContext):
    output_dir: Path
    site: Dict

    @property
    def labels(self) -> SiteLabels:
        return SiteLabels(self.site["labels"])

    @property
    def display(self) -> SiteDisplay:
        return SiteDisplay(self.site["display"])

    @property
    def defaults_dir(self) -> Path:
        return self.output_dir / CR4TE_DEFAULTS_DIR.relative_to(CR4TE_PACKAGE_DIR)
    
    @property
    def css_dir(self) -> Path:
        return self.output_dir / CR4TE_CSS_DIR.relative_to(CR4TE_PACKAGE_DIR)
        
    @property
    def js_dir(self) -> Path:
        return self.output_dir / CR4TE_JS_DIR.relative_to(CR4TE_PACKAGE_DIR)
    
    @property
    def thumbs_dir(self) -> Path:
        return self.output_dir / THUMBNAILS_DIRNAME

    @property
    def html_dir(self) -> Path:
        return self.output_dir / "html"

    @property
    def symlinks_dir(self) -> Path:
        return self.output_dir / "symlinks"

    @property
    def index_html_path(self) -> Path:
        return self.output_dir / "index.html"

    @property
    def projects_html_path(self) -> Path:
        return self.output_dir / "projects.html"

    @property
    def tags_html_path(self) -> Path:
        return self.output_dir / "tags.html"
        
    @property
    def project_page_audio_section_base_title(self) -> str:
        return self.labels.sections.audio

    @property
    def project_page_image_section_base_title(self) -> str:
        return self.labels.sections.images
        
    @property
    def fallback_tag_category(self) -> str:
        return self.labels.fallback_tag_category

    @property
    def image_gallery_sample_max(self) -> int:
        return self.display.image_gallery_sample_max

    @property
    def image_gallery_sample_strategy(self) -> str:
        return self.display.image_gallery_sample_strategy

    @property
    def media_type_order(self) -> List[str]:
        return self.display.media_type_order

    @property
    def creator_page_visible_fields(self) -> List[CreatorField]:
        return self.display.visible_fields.creator_page

    @property
    def project_page_visible_fields(self) -> List[ProjectField]:
        return self.display.visible_fields.project_page

    @property
    def metadata_labels(self) -> Dict:
        return self.labels.metadata

    @property
    def section_labels(self) -> SectionLabels:
        return self.labels.sections

    def get_default_thumb_path(self, thumb_type: ThumbType) -> Path:
        return self.defaults_dir / {
            ThumbType.THUMB: "thumb.png",
            ThumbType.PORTRAIT: "portrait.png",
            ThumbType.COVER: "cover.png",
            ThumbType.GALLERY: "thumb.png",
        }[thumb_type]
        
    def get_thumb_height(self, thumb_type: ThumbType) -> int:
        return {
            ThumbType.THUMB: 350,
            ThumbType.PORTRAIT: 720,
            ThumbType.COVER: 720,
            ThumbType.GALLERY: 450,
        }[thumb_type]

