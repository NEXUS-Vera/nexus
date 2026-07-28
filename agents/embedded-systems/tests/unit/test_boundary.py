"""Deterministic pre-check heuristics for the embedded initialization boundary."""

from __future__ import annotations

import pytest
from nexus_embedded_systems.workflows.project_initialization.boundary import (
    deterministic_boundary_check,
)


@pytest.mark.parametrize(
    "message",
    [
        "Build me a web app for tracking personal expenses.",
        "I need a mobile app for tracking my daily habits.",
        "Build a REST API backend for a todo list SaaS product.",
    ],
)
def test_software_only_prompts_are_rejected(message: str) -> None:
    within, reasons = deterministic_boundary_check(message)
    assert within is False
    assert reasons
    assert any("software-only" in reason for reason in reasons)


@pytest.mark.parametrize(
    "message",
    [
        "Why is my code not working, it keeps crashing on boot.",
        "Debug my firmware, I'm getting a compiler error I don't understand.",
        "My upload failed and I see a stack trace, can you help me fix it?",
    ],
)
def test_debugging_prompts_are_rejected(message: str) -> None:
    within, reasons = deterministic_boundary_check(message)
    assert within is False
    assert any("debugging" in reason for reason in reasons)


@pytest.mark.parametrize(
    "message",
    [
        "I need help with PCB layout for my sensor board.",
        "Can you review this schematic validation in KiCad for my design?",
        "I need help with trace routing and layer stackup for my board.",
    ],
)
def test_pcb_prompts_are_rejected(message: str) -> None:
    within, reasons = deterministic_boundary_check(message)
    assert within is False
    assert any("PCB" in reason for reason in reasons)


def test_firmware_generation_prompt_is_rejected() -> None:
    within, reasons = deterministic_boundary_check(
        "Write the firmware for reading a temperature sensor over I2C."
    )
    assert within is False
    assert any("firmware" in reason for reason in reasons)


def test_component_selection_only_prompt_is_rejected() -> None:
    within, reasons = deterministic_boundary_check(
        "Which microcontroller should I use for a battery-powered sensor?"
    )
    assert within is False
    assert any("component-selection-only" in reason for reason in reasons)


def test_factual_qa_prompt_is_rejected() -> None:
    within, reasons = deterministic_boundary_check("What is the difference between I2C and SPI?")
    assert within is False
    assert any("factual question" in reason for reason in reasons)


def test_manufacturing_and_certification_prompt_is_rejected() -> None:
    within, reasons = deterministic_boundary_check(
        "I need help planning FCC approval and mass production for my device."
    )
    assert within is False
    assert any("manufacturing, certification, or purchasing" in reason for reason in reasons)


def test_multi_product_ambiguity_is_rejected() -> None:
    within, reasons = deterministic_boundary_check(
        "I want to build a soil moisture sensor and also build a completely "
        "separate smart doorbell."
    )
    assert within is False
    assert any("more than one unrelated product" in reason for reason in reasons)


def test_empty_message_is_rejected() -> None:
    within, reasons = deterministic_boundary_check("   ")
    assert within is False
    assert reasons == ["Message is empty after normalization."]


@pytest.mark.parametrize(
    "message",
    [
        "I want to build a wrist-worn wearable device that measures hand "
        "tremors and records the motion data for later analysis.",
        "I want to build a greenhouse sensor node that measures "
        "temperature, humidity, soil moisture, and light.",
        "I want to build a small indoor robot that drives around a room "
        "and maps temperature, humidity, and air quality.",
    ],
)
def test_embedded_prompts_pass_the_deterministic_check(message: str) -> None:
    within, reasons = deterministic_boundary_check(message)
    assert within is True
    assert reasons
    assert any("embedded/physical-computing signals" in reason for reason in reasons)


def test_prompt_without_embedded_signal_still_passes_but_defers_to_llm() -> None:
    within, reasons = deterministic_boundary_check(
        "I want to build a small indoor rover that drives around a room "
        "and maps temperature, humidity, and air quality."
    )
    assert within is True
    assert any("defer to LLM interpretation" in reason for reason in reasons)


def test_ambiguous_prompt_with_no_embedded_signal_still_defers_to_llm() -> None:
    within, reasons = deterministic_boundary_check(
        "I want to build something for my house that helps me stay organized."
    )
    assert within is True
    assert any("defer to LLM interpretation" in reason for reason in reasons)


def test_word_boundary_avoids_false_positive_inside_longer_word() -> None:
    # "ble" is a substring of "wearable" but must not match the BLE keyword.
    within, reasons = deterministic_boundary_check(
        "I want to build a wearable band that logs steps."
    )
    assert within is True
    assert not any(reason.strip() == "" for reason in reasons)
