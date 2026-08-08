"""
C-UAS Layered Sensing Analysis Framework
========================================
Educational / engineering-analysis toolkit for evaluating layered
counter-UAS sensor coverage over maritime port approaches.

Scope: sensing, detection, classification and tracking performance.
This package models DETECTION physics only. It contains no operational
effector, jamming or intercept parameters by design.

Modules
-------
radar        : noise-limited radar detection (Marcum/Swerling/Albersheim)
propagation  : maritime propagation - gas + rain attenuation, sea-surface
               multipath, radar horizon
microdoppler : scatterer-based rotor / bird signature synthesis + features
tracking     : Kalman (CV) and IMM (CV+CA) filters with validation metrics
system       : layered detection probability, coverage maps, sensor siting
"""

__version__ = "0.2.0"

from . import radar, propagation, microdoppler, tracking, system  # noqa: F401

__all__ = ["radar", "propagation", "microdoppler", "tracking", "system"]
