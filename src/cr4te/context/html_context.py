from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from ..enums.thumb_type import ThumbType
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
class HtmlBuildContext(BaseContext):
    output_dir: Path
    html_settings: Dict
    
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
        return self.html_settings["project_page_audio_section_base_title"]

    @property
    def project_page_image_section_base_title(self) -> str:
        return self.html_settings["project_page_image_section_base_title"]
        
    @property
    def fallback_tag_category(self) -> str:
        return self.html_settings["fallback_tag_category"]

    @property
    def image_gallery_sample_max(self) -> int:
        return self.html_settings["image_gallery_sample_max"]

    @property
    def image_gallery_sample_strategy(self) -> str:
        return self.html_settings["image_gallery_sample_strategy"]

    @property
    def media_type_order(self) -> List[str]:
        return self.html_settings["media_type_order"]

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

