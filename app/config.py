import json
import os
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

GOOGLE_LANGUAGES = [{"code": code, "name": name} for code, name in [
    ("zh-Hans", "简体中文"), ("zh-Hant", "繁體中文"), ("en", "English"),
    ("ja", "日本語"), ("ko", "한국어"), ("es", "Español"), ("fr", "Français"), ("de", "Deutsch"),
]]


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
    translation_enabled: bool = False
    target_language: str = Field(default="zh-Hans", pattern=r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})*$")
    target_languages: list[str] | None = Field(default=None, min_length=1, max_length=8)
    style: Style = Field(default_factory=Style)

    @model_validator(mode="after")
    def normalize_target(self):
        supported = {item["code"] for item in GOOGLE_LANGUAGES}
        targets = self.target_languages or [self.target_language]
        if any(not re.fullmatch(r"[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})*", code) for code in targets):
            raise ValueError("Invalid target language")
        targets = [code for code in targets if code in supported] or ["zh-Hans"]
        self.target_languages = list(dict.fromkeys(targets))
        self.target_language = self.target_languages[0]
        return self

    def public(self):
        return self.model_dump()


class ConfigStore:
    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            values = json.loads(path.read_text("utf-8"))
            # Import old local settings without retaining obsolete modes or credentials.
            for field in ("source_type", "youtube_provider", "youtube_key", "translation_provider", "azure_key", "azure_region"):
                values.pop(field, None)
            self.config = Config.model_validate(values)
        else:
            self.config = Config()

    def save(self, config: Config):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        # Never put secrets into an API response; disk persistence is local only.
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(config.model_dump(), file, ensure_ascii=False, indent=2)
        os.replace(temp, self.path)
        self.config = config
