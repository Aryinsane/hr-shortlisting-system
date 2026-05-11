"""
app/agents/jd_parser_agent.py
==============================
LangChain-based agent for parsing Job Descriptions.
Uses GPT-4o with structured JSON output and injection protection.
"""

import json
from pathlib import Path
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config.settings import settings
from app.schemas.jd_schema import JobDescription
from app.security.malicious_prompt_detector import PromptInjectionDetector
from app.parsers.text_cleaner import clean_resume_text
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Load the JD parsing prompt template
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "jd_prompt.txt"
_JD_PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")

# Injection detector instance
_injection_detector = PromptInjectionDetector()


class JDParserAgent:
    """
    LangChain agent that parses raw JD text into a structured JobDescription object.

    Security:
    - Detects and blocks prompt injection in JD text
    - Uses structured JSON output with Pydantic validation
    - Temperature 0 to minimize hallucination
    """

    def __init__(self):
        self._llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.temperature,
            openai_api_key=settings.openai_api_key,
            max_tokens=settings.max_tokens,
        )
        logger.info("JDParserAgent initialized")

    def parse(self, jd_text: str) -> JobDescription:
        """
        Parse raw job description text into a structured JobDescription.

        Args:
            jd_text: Raw text of the job description.

        Returns:
            Validated JobDescription Pydantic object.

        Raises:
            ValueError: If injection is detected or parsing fails.
        """
        # 1. Clean text
        cleaned_text = clean_resume_text(jd_text, max_chars=6000)

        # 2. Security check — prompt injection detection
        is_malicious, patterns = _injection_detector.check(cleaned_text)
        if is_malicious:
            logger.warning(f"Prompt injection in JD: {patterns[:2]}")
            raise ValueError(
                f"SECURITY: Potential prompt injection detected in JD. "
                f"Matched patterns: {patterns[:2]}"
            )

        # 3. Build prompt
        prompt = _JD_PROMPT_TEMPLATE.replace("{jd_text}", cleaned_text)

        # 4. Call LLM
        messages = [
            SystemMessage(
                content="You are a precise HR data extraction system. "
                        "Return ONLY valid JSON. No extra text."
            ),
            HumanMessage(content=prompt),
        ]

        logger.info("Calling GPT-4o for JD parsing...")
        response = self._llm.invoke(messages)
        raw_output = response.content

        # 5. Parse and validate JSON output
        jd_data = self._parse_llm_output(raw_output)

        # 6. Validate with Pydantic
        job_description = JobDescription(**jd_data)

        logger.info(
            f"JD parsed successfully: '{job_description.title}' | "
            f"{len(job_description.required_skills)} required skills"
        )
        return job_description

    def _parse_llm_output(self, raw_output: str) -> Dict[str, Any]:
        """
        Extract and validate JSON from LLM response.
        Handles markdown code block wrappers.

        Args:
            raw_output: Raw LLM response string.

        Returns:
            Parsed dictionary.

        Raises:
            ValueError: If JSON parsing fails.
        """
        import re

        # Strip markdown code blocks
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_output.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON output: {e}\nRaw: {raw_output[:500]}")
            raise ValueError(f"LLM returned invalid JSON: {e}")

        # Check for error responses (e.g., injection detected)
        if "error" in parsed:
            raise ValueError(f"LLM error response: {parsed.get('message', 'Unknown error')}")

        return parsed


def parse_jd(jd_text: str) -> JobDescription:
    """
    Module-level convenience function for JD parsing.

    Args:
        jd_text: Raw job description text.

    Returns:
        Structured JobDescription object.
    """
    agent = JDParserAgent()
    return agent.parse(jd_text)
