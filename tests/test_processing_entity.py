"""Tests for backend/processing/entity.py"""
from __future__ import annotations

import pytest

from backend.processing.entity import EntityExtractor

GAZETTEER = {
    "manufacturers": {
        "Tesla": {
            "aliases": ["tesla", "tsla"],
            "models": {
                "Model_3": ["model 3", "model3"],
                "Model_Y": ["model y", "modely"],
                "Cybertruck": ["cybertruck"],
            },
        },
        "Hyundai": {
            "aliases": ["hyundai"],
            "models": {
                "Ioniq5": ["ioniq 5", "ioniq5"],
            },
        },
        "Ford": {
            "aliases": ["ford"],
            "models": {
                "Mustang_Mach_E": ["mach-e", "mach e"],
                "F150_Lightning": ["f-150 lightning", "lightning"],
            },
        },
    },
    "vehicle_types": {
        "SUV":     ["suv", "crossover"],
        "Sedan":   ["sedan"],
        "Pickup":  ["pickup truck", "pickup"],
    },
    "model_year_pattern": r"\b(20[1-3]\d)\b",
}


@pytest.fixture()
def ext():
    return EntityExtractor(GAZETTEER)


# ── Manufacturer detection ────────────────────────────────────────────────────

def test_tesla_detected(ext):
    r = ext.extract("My Tesla Model 3 has great battery life")
    assert r.manufacturer == "Tesla"


def test_hyundai_detected(ext):
    r = ext.extract("My Hyundai Ioniq 5 is a great EV")
    assert r.manufacturer == "Hyundai"


def test_tsla_alias_detected(ext):
    r = ext.extract("TSLA owner here — the charging speed is amazing")
    assert r.manufacturer == "Tesla"


def test_no_manufacturer_returns_none(ext):
    r = ext.extract("I drove my car to the charging station today")
    assert r.manufacturer is None


# ── Model detection ───────────────────────────────────────────────────────────

def test_model_3_detected(ext):
    r = ext.extract("I own a Tesla Model 3 long range version")
    assert r.manufacturer == "Tesla"
    assert r.vehicle_model == "Model_3"


def test_ioniq5_detected(ext):
    r = ext.extract("My Hyundai Ioniq 5 battery is at 95% after 2 years")
    assert r.vehicle_model == "Ioniq5"


def test_mach_e_detected(ext):
    r = ext.extract("The Ford Mach-E has great range for an SUV")
    assert r.manufacturer == "Ford"
    assert r.vehicle_model == "Mustang_Mach_E"


def test_model_not_detected_without_manufacturer(ext):
    """Model 3 should only be assigned under Tesla manufacturer."""
    r = ext.extract("The Model 3 is impressive")
    # Manufacturer must be detected for model to be assigned
    # Even if model string matches, manufacturer "Tesla" must appear
    if r.manufacturer is None:
        assert r.vehicle_model is None
    # OR manufacturer was detected via alias — either way, model should be set
    if r.manufacturer == "Tesla":
        assert r.vehicle_model == "Model_3"


def test_no_model_returns_none(ext):
    r = ext.extract("Tesla makes great vehicles but I have a different one")
    assert r.manufacturer == "Tesla"
    assert r.vehicle_model is None


# ── Model year ────────────────────────────────────────────────────────────────

def test_year_2023_detected(ext):
    r = ext.extract("My 2023 Tesla Model 3 has been excellent so far")
    assert r.model_year == 2023


def test_year_2019_detected(ext):
    r = ext.extract("Bought a 2019 Hyundai, still going strong")
    assert r.model_year == 2019


def test_no_year_returns_none(ext):
    r = ext.extract("My Tesla has great range and performance")
    assert r.model_year is None


def test_year_out_of_range_not_matched(ext):
    r = ext.extract("My 2009 car is old and the 1998 model was worse")
    assert r.model_year is None


# ── Vehicle type ──────────────────────────────────────────────────────────────

def test_suv_detected(ext):
    r = ext.extract("Great SUV for family trips with good range")
    assert r.vehicle_type == "SUV"


def test_crossover_detected_as_suv(ext):
    r = ext.extract("This crossover has excellent charging speed")
    assert r.vehicle_type == "SUV"


def test_sedan_detected(ext):
    r = ext.extract("The sedan version has better aerodynamics")
    assert r.vehicle_type == "Sedan"


def test_pickup_detected(ext):
    r = ext.extract("This pickup truck tows well but range suffers")
    assert r.vehicle_type == "Pickup"


def test_no_vehicle_type_returns_none(ext):
    r = ext.extract("My vehicle has a great battery and fast charging speed")
    assert r.vehicle_type is None


# ── Empty input ───────────────────────────────────────────────────────────────

def test_none_input_returns_empty_result(ext):
    r = ext.extract(None)
    assert r.manufacturer is None
    assert r.vehicle_model is None
    assert r.model_year is None
    assert r.vehicle_type is None


def test_empty_string_returns_empty_result(ext):
    r = ext.extract("")
    assert r.manufacturer is None


# ── Never guesses ─────────────────────────────────────────────────────────────

def test_no_guessing_ambiguous_text(ext):
    """Ambiguous text with no clear match must return all None."""
    r = ext.extract(
        "I really enjoy driving my electric vehicle on long road trips."
    )
    assert r.manufacturer is None
    assert r.vehicle_model is None
