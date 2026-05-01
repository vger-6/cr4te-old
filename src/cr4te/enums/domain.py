from enum import Enum

class Domain(str, Enum):
    CREATOR = "creator"
    ART = "art"
    MUSIC = "music"
    FILM = "film"
    BOOK = "book"
    MODEL = "model"
