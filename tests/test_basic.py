"""Smoke tests against config.example.yaml (no config.yaml needed)."""
from meeting_minutes import config, gather, keywords as kw
from meeting_minutes.classify import classify, parse_date, slugify


def test_config_loads_example():
    cfg = config.load()
    assert cfg["backend"] in {"notebooklm", "cloud", "local"}
    assert cfg["paths"]["audio_dir"].startswith("/")  # expanded ~


def test_classify_account_from_config():
    cfg = config.load()
    assert classify("acme sync 2026.01.15.m4a", cfg)["account"] == "AcmeCorp"
    assert classify("globex 环球 2026.02.20.m4a", cfg)["account"] == "Globex"
    assert classify("random startup 2026.03.01.m4a", cfg)["account"] == "_Uncategorized"


def test_date_and_slug():
    assert parse_date("acme 2026.01.15.m4a") == "2026.01.15"
    assert parse_date("acme 2026_01_15.m4a") == "2026.01.15"
    assert slugify("Acme Sync 2026.01.15") == "acme-sync"


def test_minutes_path_uses_account_subfolder():
    cfg = config.load()
    p = gather.minutes_path("acme 2026.01.15.m4a", cfg)
    assert p.parent.name == "AcmeCorp" and p.name == "acme 2026.01.15.md"


def test_glossary_from_example_minutes():
    text = open("examples/AcmeCorp 2026.01.15.md", encoding="utf-8").read()
    g = kw.extract_keywords(text)
    assert "AcmeCorp" in g and any("SOC" in t for t in g)


def test_local_backend_summary_prompt_includes_transcript_and_glossary():
    from meeting_minutes import run
    ctx = {"title": "AcmeCorp 2026.01.15", "account": "AcmeCorp", "date": "2026.01.15",
           "org": "Your Company", "glossary": "AcmeCorp, SOC 2"}
    p = run._build_summary_prompt("Jane: latency is too high.", ctx)
    assert "Jane: latency is too high." in p and "AcmeCorp, SOC 2" in p
    assert "{transcript}" not in p and "Your Company" in p


def test_config_defaults_whisper_turbo():
    cfg = config.load()
    assert cfg["local"]["whisper_model"] == "large-v3-turbo"
    assert "model" in cfg["llm"]
