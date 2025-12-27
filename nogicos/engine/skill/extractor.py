# -*- coding: utf-8 -*-
"""
Parameter Extractor - Extract parameters from task descriptions

Two approaches:
    1. Rule-based extraction (fast, no LLM cost)
    2. LLM-based extraction (accurate, for complex cases)

Flow:
    1. Receive task description + skill definition
    2. Try rule-based extraction first
    3. Fall back to LLM if needed
    4. Return extracted parameters

Reference: SkillWeaver paper (arXiv:2504.07079)
"""

import re
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger("nogicos.skill.extractor")


# =============================================================================
# LLM Prompt for Parameter Extraction
# =============================================================================

EXTRACT_PARAMS_PROMPT = '''You are an expert at extracting parameters from natural language task descriptions.

## Skill Definition

**Function:** {function_name}
**Description:** {description}
**Parameters:**
{parameters}

## User Task

{task}

## Instructions

Extract the parameter values from the user's task that correspond to the skill's parameters.
Return ONLY a valid JSON object with parameter names as keys and extracted values as values.
If a parameter cannot be determined from the task, use null.

## Example

For a skill with parameter "query: str" and task "Search for AI news on the website":
{{"query": "AI news"}}

## Your Response (JSON only):
'''


@dataclass
class ExtractionResult:
    """Result of parameter extraction"""
    success: bool
    params: Dict[str, Any]
    method: str = "unknown"  # "rule" or "llm"
    error: Optional[str] = None


# =============================================================================
# Rule-Based Extraction Patterns
# =============================================================================

# Common patterns for extracting values from task descriptions
EXTRACTION_PATTERNS = {
    # Search/query patterns
    "query": [
        r'search (?:for )?"?([^"]+?)"? (?:on|in|at)',  # "search for X on/in"
        r'search (?:for )?"?([^"]+?)"?$',               # "search for X"
        r'find "?([^"]+?)"? (?:on|in|at)',              # "find X on/in"
        r'look (?:for|up) "?([^"]+?)"?',                # "look for/up X"
        r'"([^"]+)"',                                    # Quoted string
    ],
    
    # URL patterns
    "url": [
        r'(?:go to|navigate to|open) (https?://[^\s]+)',
        r'(https?://[^\s]+)',
    ],
    
    # Username patterns
    "username": [
        r'(?:as |user(?:name)? )["\']?(\w+)["\']?',
        r'login (?:with |as )["\']?(\w+)["\']?',
    ],
    
    # Email patterns
    "email": [
        r'[\w\.-]+@[\w\.-]+\.\w+',
    ],
    
    # Number patterns
    "count": [
        r'(\d+) (?:items?|results?|pages?)',
        r'(?:first|top) (\d+)',
    ],
    "limit": [
        r'limit (?:to )?(\d+)',
        r'(\d+) (?:items?|results?)',
    ],
}


def extract_by_rules(task: str, param_name: str, param_type: str = "str") -> Optional[str]:
    """
    Extract parameter value using rule-based patterns
    
    Args:
        task: Task description
        param_name: Parameter name
        param_type: Parameter type (str, int, float, bool)
    
    Returns:
        Extracted value or None
    """
    task_lower = task.lower()
    
    # Get patterns for this parameter name
    patterns = EXTRACTION_PATTERNS.get(param_name, [])
    
    # Also try generic patterns based on parameter name
    if not patterns:
        # Try to find quoted values for string params
        if param_type == "str":
            patterns = [
                r'"([^"]+)"',  # Double quoted
                r"'([^']+)'",  # Single quoted
            ]
    
    for pattern in patterns:
        match = re.search(pattern, task_lower, re.IGNORECASE)
        if match:
            value = match.group(1)
            
            # Type conversion
            if param_type == "int":
                try:
                    return int(value)
                except:
                    continue
            elif param_type == "float":
                try:
                    return float(value)
                except:
                    continue
            elif param_type == "bool":
                return value.lower() in ("true", "yes", "1", "on")
            else:
                return value
    
    return None


def extract_quoted_strings(task: str) -> List[str]:
    """Extract all quoted strings from task"""
    results = []
    # Double quotes
    results.extend(re.findall(r'"([^"]+)"', task))
    # Single quotes
    results.extend(re.findall(r"'([^']+)'", task))
    return results


# =============================================================================
# Parameter Extractor Class
# =============================================================================

class ParameterExtractor:
    """
    Extract parameters from task descriptions for skill execution
    
    Usage:
        extractor = ParameterExtractor()
        result = await extractor.extract(
            task="Search for AI news on Hacker News",
            skill_params=[{"name": "query", "type": "str"}],
        )
        print(result.params)  # {"query": "AI news"}
    """
    
    def __init__(
        self,
        llm=None,
        prefer_rules: bool = True,
    ):
        """
        Initialize extractor
        
        Args:
            llm: Optional LLM for complex extraction
            prefer_rules: Try rule-based extraction first
        """
        self._llm = llm
        self.prefer_rules = prefer_rules
    
    @property
    def llm(self):
        """Lazy LLM initialization"""
        if self._llm is None:
            from langchain_anthropic import ChatAnthropic
            import os
            
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                return None  # Return None if no API key
            
            self._llm = ChatAnthropic(
                model="claude-sonnet-4-20250514",  # Use Haiku for cheap extraction
                api_key=api_key,
                max_tokens=256,
            )
        return self._llm
    
    async def extract(
        self,
        task: str,
        skill_name: str = "",
        skill_description: str = "",
        skill_params: List[Dict[str, str]] = None,
    ) -> ExtractionResult:
        """
        Extract parameters from task description
        
        Args:
            task: Task description
            skill_name: Skill function name
            skill_description: Skill description
            skill_params: List of parameter definitions [{name, type, description}]
        
        Returns:
            ExtractionResult with extracted parameters
        """
        skill_params = skill_params or []
        
        if not skill_params:
            return ExtractionResult(
                success=True,
                params={},
                method="none",
            )
        
        # Try rule-based extraction first
        if self.prefer_rules:
            params, all_extracted = self._extract_by_rules(task, skill_params)
            
            if all_extracted:
                logger.info(f"[Extractor] Rule-based extraction success: {params}")
                return ExtractionResult(
                    success=True,
                    params=params,
                    method="rule",
                )
        
        # Fall back to LLM if needed
        if self.llm:
            return await self._extract_by_llm(task, skill_name, skill_description, skill_params)
        
        # Return partial rule-based results if LLM not available
        params, _ = self._extract_by_rules(task, skill_params)
        return ExtractionResult(
            success=len(params) > 0,
            params=params,
            method="rule_partial",
        )
    
    def _extract_by_rules(
        self,
        task: str,
        skill_params: List[Dict[str, str]],
    ) -> tuple[Dict[str, Any], bool]:
        """
        Try to extract all parameters using rules
        
        Returns:
            (params dict, all_extracted bool)
        """
        params = {}
        all_extracted = True
        
        # Get quoted strings as potential values
        quoted = extract_quoted_strings(task)
        quoted_idx = 0
        
        for param in skill_params:
            name = param.get("name", "")
            ptype = param.get("type", "str")
            required = param.get("required", True)
            default = param.get("default")
            
            # Try rule-based extraction
            value = extract_by_rules(task, name, ptype)
            
            # Fall back to quoted strings for string params
            if value is None and ptype == "str" and quoted_idx < len(quoted):
                value = quoted[quoted_idx]
                quoted_idx += 1
            
            if value is not None:
                params[name] = value
            elif default is not None:
                params[name] = default
            elif required:
                all_extracted = False
        
        return params, all_extracted
    
    async def _extract_by_llm(
        self,
        task: str,
        skill_name: str,
        skill_description: str,
        skill_params: List[Dict[str, str]],
    ) -> ExtractionResult:
        """
        Extract parameters using LLM
        """
        # Format parameters for prompt
        params_str = "\n".join([
            f"  - {p['name']}: {p.get('type', 'str')} - {p.get('description', '')}"
            for p in skill_params
        ])
        
        prompt = EXTRACT_PARAMS_PROMPT.format(
            function_name=skill_name,
            description=skill_description,
            parameters=params_str,
            task=task,
        )
        
        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()
            
            # Parse JSON response
            import json
            
            # Handle markdown code blocks
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])
            
            params = json.loads(content)
            
            # Filter out null values
            params = {k: v for k, v in params.items() if v is not None}
            
            logger.info(f"[Extractor] LLM extraction success: {params}")
            return ExtractionResult(
                success=True,
                params=params,
                method="llm",
            )
            
        except Exception as e:
            logger.error(f"[Extractor] LLM extraction failed: {e}")
            return ExtractionResult(
                success=False,
                params={},
                method="llm",
                error=str(e),
            )
    
    def extract_from_skill(
        self,
        task: str,
        skill: "Skill",
    ) -> ExtractionResult:
        """
        Extract parameters for a Skill object
        
        Synchronous method using rules only.
        """
        from engine.knowledge.store import Skill, SkillParameter
        
        if not isinstance(skill, Skill):
            return ExtractionResult(
                success=False,
                params={},
                error="Invalid skill object",
            )
        
        # Convert SkillParameter to dict format
        skill_params = [
            {
                "name": p.name,
                "type": p.param_type,
                "description": p.description,
                "required": p.required,
                "default": p.default,
            }
            for p in skill.parameters
        ]
        
        params, all_extracted = self._extract_by_rules(task, skill_params)
        
        return ExtractionResult(
            success=all_extracted or len(params) > 0,
            params=params,
            method="rule" if all_extracted else "rule_partial",
        )


# =============================================================================
# Quick Test
# =============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test_extractor():
        print("=" * 50)
        print("Parameter Extractor Test")
        print("=" * 50)
        
        extractor = ParameterExtractor()
        
        # Test 1: Simple search query
        print("\n[1] Testing search query extraction...")
        result = await extractor.extract(
            task='Search for "AI news" on Hacker News',
            skill_name="search_hn",
            skill_description="Search on Hacker News",
            skill_params=[{"name": "query", "type": "str"}],
        )
        print(f"    Success: {result.success}")
        print(f"    Params: {result.params}")
        print(f"    Method: {result.method}")
        
        # Test 2: Multiple quoted strings
        print("\n[2] Testing multiple parameters...")
        result = await extractor.extract(
            task='Login with username "testuser" and password "secret123"',
            skill_name="login",
            skill_description="Login to website",
            skill_params=[
                {"name": "username", "type": "str"},
                {"name": "password", "type": "str"},
            ],
        )
        print(f"    Success: {result.success}")
        print(f"    Params: {result.params}")
        
        # Test 3: Number extraction
        print("\n[3] Testing number extraction...")
        result = await extractor.extract(
            task="Get the first 10 results",
            skill_name="get_results",
            skill_description="Get search results",
            skill_params=[{"name": "count", "type": "int"}],
        )
        print(f"    Success: {result.success}")
        print(f"    Params: {result.params}")
        
        # Test 4: URL extraction
        print("\n[4] Testing URL extraction...")
        result = await extractor.extract(
            task="Go to https://news.ycombinator.com and get headlines",
            skill_name="get_headlines",
            skill_description="Get headlines from URL",
            skill_params=[{"name": "url", "type": "str"}],
        )
        print(f"    Success: {result.success}")
        print(f"    Params: {result.params}")
        
        # Test 5: Default values
        print("\n[5] Testing default values...")
        result = await extractor.extract(
            task="Search the website",  # No query specified
            skill_name="search",
            skill_description="Search",
            skill_params=[
                {"name": "query", "type": "str", "required": False, "default": "*"}
            ],
        )
        print(f"    Success: {result.success}")
        print(f"    Params: {result.params}")
        
        print("\n" + "=" * 50)
        print("Extractor Test Complete!")
        print("=" * 50)
    
    asyncio.run(test_extractor())

