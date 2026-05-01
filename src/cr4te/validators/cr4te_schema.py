from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from typing import Any, Dict, List
import re

from ..enums.domain import Domain
from ..enums.creator_type import CreatorType

__all__ = ["get_domain_meta_model", "get_domain_meta_fields", "build_domain_meta"]


def _validate_optional_iso_date(v: str) -> str:
    if not v:
        return v

    v = v.strip()

    if re.fullmatch(r"\d{4}", v):
        return v
    if re.fullmatch(r"\d{4}-\d{2}", v):
        return v
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return v

    raise ValueError(f"{v} must be in yyyy, yyyy-mm, yyyy-mm-dd format or empty")


def _validate_date_order(start: str, end: str, field_names: str):
    if start and end and start > end:
        raise ValueError(f"{field_names} are in invalid chronological order")


class BaseDatedModel(BaseModel):
    @field_validator(
        "date_of_birth",
        "date_of_death",
        "founding_date",
        "dissolution_date",
        mode="before",
        check_fields=False,
    )
    def validate_dates(cls, v):
        if isinstance(v, str):
            return _validate_optional_iso_date(v)
        return v

class Person(BaseDatedModel):
    date_of_birth: str = ""
    date_of_death: str = ""
    civil_name: str = ""

    @model_validator(mode="after")
    def check_person_dates(self):
        _validate_date_order(self.date_of_birth, self.date_of_death, "date_of_birth/date_of_death")
        return self


class Collaboration(BaseDatedModel):
    founding_date: str = ""
    dissolution_date: str = ""
    members: List[str]

    @model_validator(mode="after")
    def check_collab_dates(self):
        _validate_date_order(self.founding_date, self.dissolution_date, "founding_date/dissolution_date")
        return self


class Video(BaseModel):
    file: str
    poster: str

    class Config:
        extra = "forbid"


class MediaGroup(BaseModel):
    is_root: bool
    videos: List[Video]
    tracks: List[str]
    images: List[str]
    documents: List[str]
    texts: List[str]
    rel_dir_path: str

    class Config:
        extra = "forbid"


class DomainMetaBase(BaseModel):
    class Config:
        extra = "forbid"


class EmptyMeta(DomainMetaBase):
    pass


class ModelMeta(DomainMetaBase):
    photographers: List[str] = Field(default_factory=list)
    studios: List[str] = Field(default_factory=list)
    designers: List[str] = Field(default_factory=list)
    poses: List[str] = Field(default_factory=list)
    makeup_artists: List[str] = Field(default_factory=list)
    stylists: List[str] = Field(default_factory=list)
    brands: List[str] = Field(default_factory=list)
    magazines: List[str] = Field(default_factory=list)


class BookMeta(DomainMetaBase):
    languages: List[str] = Field(default_factory=list)
    publishers: List[str] = Field(default_factory=list)
    editors: List[str] = Field(default_factory=list)
    translators: List[str] = Field(default_factory=list)
    isbns: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    cover_artists: List[str] = Field(default_factory=list)
    genres: List[str] = Field(default_factory=list)


class FilmMeta(DomainMetaBase):
    actors: List[str] = Field(default_factory=list)
    producers: List[str] = Field(default_factory=list)
    cinematographers: List[str] = Field(default_factory=list)
    score_composers: List[str] = Field(default_factory=list)
    editors: List[str] = Field(default_factory=list)
    genres: List[str] = Field(default_factory=list)
    visual_effects: List[str] = Field(default_factory=list)
    studios: List[str] = Field(default_factory=list)
    writers: List[str] = Field(default_factory=list)
    costume_designers: List[str] = Field(default_factory=list)


class MusicMeta(DomainMetaBase):
    musicians: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    studios: List[str] = Field(default_factory=list)
    genres: List[str] = Field(default_factory=list)
    instruments: List[str] = Field(default_factory=list)
    producers: List[str] = Field(default_factory=list)
    cover_artists: List[str] = Field(default_factory=list)


class ArtMeta(DomainMetaBase):
    mediums: List[str] = Field(default_factory=list)
    materials: List[str] = Field(default_factory=list)
    exhibitions: List[str] = Field(default_factory=list)
    periods: List[str] = Field(default_factory=list)


DOMAIN_META_MODELS = {
    Domain.CREATOR: EmptyMeta,
    Domain.MODEL: ModelMeta,
    Domain.BOOK: BookMeta,
    Domain.FILM: FilmMeta,
    Domain.MUSIC: MusicMeta,
    Domain.ART: ArtMeta,
}


def _coerce_domain(domain: Any) -> Domain:
    if isinstance(domain, Domain):
        return domain
    if isinstance(domain, str):
        return Domain(domain)
    return Domain.CREATOR


def get_domain_meta_model(domain: Domain) -> type[DomainMetaBase]:
    return DOMAIN_META_MODELS.get(_coerce_domain(domain), EmptyMeta)


def get_domain_meta_fields(domain: Domain) -> set[str]:
    return set(get_domain_meta_model(domain).model_fields)


def build_domain_meta(domain: Domain, domain_meta: Dict[str, Any] | None) -> Dict[str, Any]:
    if domain_meta is None:
        domain_meta = {}
    model = get_domain_meta_model(domain).model_validate(domain_meta)
    return model.model_dump()


def _validate_domain_meta(domain_meta: Any, domain: Domain) -> Dict[str, Any]:
    if domain_meta is None:
        return {}
    if not isinstance(domain_meta, dict):
        raise ValueError("domain_meta must be a dictionary")

    try:
        return build_domain_meta(domain, domain_meta)
    except ValidationError as e:
        error_lines = [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
        formatted = "\n".join(error_lines)
        raise ValueError(f"domain_meta validation failed for domain '{domain.value}':\n{formatted}") from e


class Project(BaseModel):
    title: str
    release_date: str
    cover: str
    info: str
    tags: List[str]
    media_groups: List[MediaGroup]
    domain_meta: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("release_date", mode="before")
    def validate_release_date(cls, v):
        return _validate_optional_iso_date(v)

    @field_validator("domain_meta", mode="before")
    def validate_domain_meta_shape(cls, v):
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError("domain_meta must be a dictionary")
        return v

    @model_validator(mode="after")
    def validate_project_domain_meta(self, info):
        domain = _coerce_domain((info.context or {}).get("domain"))
        try:
            self.domain_meta = _validate_domain_meta(self.domain_meta, domain)
        except ValueError as e:
            raise ValueError(str(e)) from e
        return self

    class Config:
        extra = "forbid"


class Creator(BaseModel):
    name: str
    type: CreatorType
    active_since: str
    person: Person
    collaboration: Collaboration
    nationality: str
    aliases: List[str]
    portrait: str
    info: str
    tags: List[str]
    projects: List[Project]
    media_groups: List[MediaGroup]
    collaborations: List[str]

    @model_validator(mode="after")
    def enforce_type_consistency(self):
        if self.type == CreatorType.PERSON:
            if any([
                self.collaboration.founding_date,
                self.collaboration.dissolution_date,
                len(self.collaboration.members) > 0,
            ]):
                raise ValueError("person creator must not have collaboration data")

        elif self.type == CreatorType.COLLABORATION:
            if any([
                self.person.date_of_birth,
                self.person.date_of_death,
                self.person.civil_name,
            ]):
                raise ValueError("collaboration must not have person data")

        return self

    class Config:
        extra = "forbid"
