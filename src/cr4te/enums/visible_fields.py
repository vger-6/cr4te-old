from enum import Enum

class CreatorField(str, Enum):
    DATE_OF_BIRTH = "date_of_birth"
    DATE_OF_DEATH = "date_of_death"
    NATIONALITY = "nationality"
    CIVIL_NAME = "civil_name"
    ALIASES = "aliases"
    DEBUT_AGE = "debut_age"
    AGE_AT_TIME = "age_at_time"
    ACTIVE_SINCE = "active_since"
    MEMBERS = "members"
    FOUNDING_DATE = "founding_date"
    DISSOLUTION_DATE = "dissolution_date"

class ProjectField(str, Enum):
    RELEASE_DATE = "release_date"
