import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Style(BaseModel):
    model_config = ConfigDict(extra="forbid")
    font_size: int = Field(default=24, ge=10, le=72)
    color: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    translation_color: str = Field(default="#8de1cb", pattern=r"^#[0-9a-fA-F]{6}$")
    show_avatar: bool = True
    max_messages: int = Field(default=100, ge=10, le=500)
    custom_css: str = Field(default="", max_length=50000)


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(default="", max_length=2048)
    source_type: str = Field(default="auto", pattern=r"^(auto|video|chat)$")
    youtube_key: str = Field(default="", max_length=512, repr=False)
    translation_enabled: bool = False
    azure_key: str = Field(default="", max_length=512, repr=False)
    azure_region: str = Field(default="", max_length=64, pattern=r"^[a-zA-Z0-9-]*$")
    target_language: str = Field(default="zh-Hans", pattern=r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})*$")
    style: Style = Field(default_factory=Style)

    def public(self):
        values = self.model_dump(exclude={"youtube_key", "azure_key"})
        values.update(youtube_key_set=bool(self.youtube_key), azure_key_set=bool(self.azure_key))
        return values


class ConfigStore:
    def __init__(self, path: Path):
        self.path = path
        self.config = Config.model_validate_json(path.read_text("utf-8")) if path.exists() else Config()

    def save(self, config: Config):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        # Never put secrets into an API response; disk persistence is local only.
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(config.model_dump(), file, ensure_ascii=False, indent=2)
        os.replace(temp, self.path)
        self.config = config
