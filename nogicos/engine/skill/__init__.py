# -*- coding: utf-8 -*-
"""
Skill Module - SkillWeaver-style skill synthesis and execution

This module provides:
    - SkillSynthesizer: Generate parameterized Python code from trajectories
    - SkillExecutor: Execute skills with parameters
    - ParameterExtractor: Extract parameters from task descriptions

Based on SkillWeaver paper (arXiv:2504.07079) with ExpeL-style confidence weighting.
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    "SkillSynthesizer",
    "SkillExecutor", 
    "ParameterExtractor",
]


def __getattr__(name):
    """Lazy module loading"""
    if name == "SkillSynthesizer":
        from engine.skill.synthesizer import SkillSynthesizer
        return SkillSynthesizer
    elif name == "SkillExecutor":
        from engine.skill.executor import SkillExecutor
        return SkillExecutor
    elif name == "ParameterExtractor":
        from engine.skill.extractor import ParameterExtractor
        return ParameterExtractor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

