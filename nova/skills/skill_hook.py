# -*- coding: utf-8 -*-
# @Time   : 2026/02/25 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
import os
import re
from pathlib import PurePosixPath
from typing import List, cast

import yaml

from nova.model.skill import SkillMetadata

logger = logging.getLogger(__name__)

# Security: Maximum size for SKILL.md files to prevent DoS attacks (10MB)
MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024

MAX_SKILL_NAME_LENGTH = 64
MAX_SKILL_DESCRIPTION_LENGTH = 1024

SKILLS_SYSTEM_PROMPT = """

## Skills System

You have access to a skills library that provides specialized capabilities and domain knowledge.

{skills_locations}

**Available Skills:**

{skills_list}

**How to Use Skills (Progressive Disclosure):**

Skills follow a **progressive disclosure** pattern - you see their name and description above, but only read full instructions when needed:

1. **Recognize when a skill applies**: Check if the user's task matches a skill's description
2. **Read the skill's full instructions**: Use the path shown in the skill list above
3. **Follow the skill's instructions**: SKILL.md contains step-by-step workflows, best practices, and examples
4. **Access supporting files**: Skills may include helper scripts, configs, or reference docs - use absolute paths

**When to Use Skills:**
- User's request matches a skill's domain (e.g., "research X" -> web-research skill)
- You need specialized knowledge or structured workflows
- A skill provides proven patterns for complex tasks

**Executing Skill Scripts:**
Skills may contain Python scripts or other executable files. Always use absolute paths from the skill list.

**Example Workflow:**

User: "Can you research the latest developments in quantum computing?"

1. Check available skills -> See "web-research" skill with its path
2. Read the skill using the path shown
3. Follow the skill's research workflow (search -> organize -> synthesize)
4. Use any helper scripts with absolute paths

Remember: Skills make you more capable and consistent. When in doubt, check if a skill exists for the task!
"""


class SkillsProvider:
    """
    技能模块，加载技能所有信息，在需要的话可以按需获取

    1. get_list_skills(self, dir) -> list[SkillMetadata]: 技能列表

    2. get_skill_prompt_template(): 获取skill的system prompt模板
    """

    def __init__(self, skill_template_dir: str) -> None:
        self.skill_template_dir = skill_template_dir
        self.system_prompt_template = SKILLS_SYSTEM_PROMPT
        self.skills = self.get_list_skills()

    def get_list_skills(self, dir=None) -> list[SkillMetadata]:
        """List all skills from a backend source.

        Scans backend for subdirectories containing SKILL.md files, downloads their content,
        parses YAML frontmatter, and returns skill metadata.

        Expected structure:
            source_path/
            ├── skill-name/
            │   ├── SKILL.md        # Required
            │   └── helper.py       # Optional

        Args:
            backend: Backend instance to use for file operations
            source_path: Path to the skills directory in the backend

        Returns:
            List of skill metadata from successfully parsed SKILL.md files
        """
        base_path = dir

        skills: list[SkillMetadata] = []
        items = self._ls_info(base_path)
        # Find all skill directories (directories containing SKILL.md)
        skill_dirs = []
        for item in items:
            if not item.get("is_dir"):
                continue
            skill_dirs.append(item["path"])

        if not skill_dirs:
            return []

        # For each skill directory, check if SKILL.md exists and download it
        skill_md_paths = []
        for skill_dir_path in skill_dirs:
            # Construct SKILL.md path using PurePosixPath for safe, standardized path operations
            skill_dir = PurePosixPath(skill_dir_path)
            skill_md_path = str(skill_dir / "SKILL.md")
            skill_md_paths.append((skill_dir_path, skill_md_path))

        paths_to_download = [skill_md_path for _, skill_md_path in skill_md_paths]
        responses = self._read_skill_mds(paths_to_download)

        # Parse each downloaded SKILL.md
        for (skill_dir_path, skill_md_path), response in zip(
            skill_md_paths, responses, strict=True
        ):
            if response.get("error"):
                # Skill doesn't have a SKILL.md, skip it
                continue

            if response.get("content") is None:
                logger.warning("skill file %s has no content", skill_md_path)
                continue

            try:
                content = cast(str, response.get("content"))
            except UnicodeDecodeError as e:
                logger.warning("Error decoding %s: %s", skill_md_path, e)
                continue

            # Extract directory name from path using PurePosixPath
            directory_name = PurePosixPath(skill_dir_path).name

            # Parse metadata
            skill_metadata = self._parse_skill_metadata(
                content=content,
                skill_path=skill_md_path,
                directory_name=directory_name,
            )
            if skill_metadata:
                skills.append(skill_metadata)

        return skills

    def get_skill_prompt_template(self) -> str:

        skills_list = self._format_skills_list(self.skills)
        skills_system_prompt = self.system_prompt_template.format(
            skills_locations=self.skill_template_dir,
            skills_list=skills_list,
        )

        return skills_system_prompt

    def _ls_info(self, path) -> list:
        """
        同步获取指定路径下的文件/目录信息
        Args:
            path: 标准化后的 Path 对象
        Returns:
            包含文件/目录路径的字典列表（格式：[{"path": "完整路径"}, ...]）
        """
        file_infos = []
        try:
            # 遍历路径下的所有条目（文件+目录）
            for entry in os.scandir(path):
                if entry.is_dir():
                    file_infos.append({"path": entry.path, "is_dir": True})
                else:
                    file_infos.append({"path": entry.path, "is_dir": False})

        # 捕获常见异常，返回友好提示（而非直接崩溃）
        except FileNotFoundError:
            raise FileNotFoundError(f"路径不存在：{path}")
        except PermissionError:
            raise PermissionError(f"无权限访问路径：{path}")
        except Exception as e:
            raise RuntimeError(f"读取路径失败：{str(e)}")

        return file_infos

    def _read_skill_mds(self, paths) -> List[dict]:
        result = []
        for path in paths:
            if not path.endswith(".md"):
                continue
            try:
                re = self._read_skill_md(path)
                result.append({"path": path, "content": re, "error": None})
            except Exception as e:
                result.append({"path": path, "content": None, "error": str(e)})

        return result

    def _read_skill_md(self, path) -> str:
        try:
            with open(path, "r") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"路径不存在：{path}")
        except PermissionError:
            raise PermissionError(f"无权限访问路径：{path}")
        except Exception as e:
            raise RuntimeError(f"读取路径失败：{str(e)}")

    def _validate_skill_name(self, name: str, directory_name: str) -> tuple[bool, str]:
        """Validate skill name per Agent Skills specification.

        Requirements per spec:
        - Max 64 characters
        - Lowercase alphanumeric and hyphens only (a-z, 0-9, -)
        - Cannot start or end with hyphen
        - No consecutive hyphens
        - Must match parent directory name

        Args:
            name: Skill name from YAML frontmatter
            directory_name: Parent directory name

        Returns:
            (is_valid, error_message) tuple. Error message is empty if valid.
        """
        if not name:
            return False, "name is required"
        if len(name) > MAX_SKILL_NAME_LENGTH:
            return False, "name exceeds 64 characters"
        # Pattern: lowercase alphanumeric, single hyphens between segments, no start/end hyphen
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
            return False, "name must be lowercase alphanumeric with single hyphens only"
        if name != directory_name:
            return False, f"name '{name}' must match directory name '{directory_name}'"
        return True, ""

    def _parse_skill_metadata(
        self, content: str, skill_path: str, directory_name: str
    ) -> SkillMetadata | None:
        """Parse YAML frontmatter from SKILL.md content.

        Extracts metadata per Agent Skills specification from YAML frontmatter delimited
        by --- markers at the start of the content.

        Args:
            content: Content of the SKILL.md file
            skill_path: Path to the SKILL.md file (for error messages and metadata)
            directory_name: Name of the parent directory containing the skill

        Returns:
            SkillMetadata if parsing succeeds, None if parsing fails or validation errors occur
        """
        if len(content) > MAX_SKILL_FILE_SIZE:
            logger.warning(
                "Skipping %s: content too large (%d bytes)", skill_path, len(content)
            )
            return None

        # Match YAML frontmatter between --- delimiters
        frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            logger.warning("Skipping %s: no valid YAML frontmatter found", skill_path)
            return None

        frontmatter_str = match.group(1)

        # Parse YAML using safe_load for proper nested structure support
        try:
            frontmatter_data = yaml.safe_load(frontmatter_str)
        except yaml.YAMLError as e:
            logger.warning("Invalid YAML in %s: %s", skill_path, e)
            return None

        if not isinstance(frontmatter_data, dict):
            logger.warning("Skipping %s: frontmatter is not a mapping", skill_path)
            return None

        # Validate required fields
        name = frontmatter_data.get("name")
        description = frontmatter_data.get("description")

        if not name or not description:
            logger.warning(
                "Skipping %s: missing required 'name' or 'description'", skill_path
            )
            return None

        # Validate name format per spec (warn but continue loading for backwards compatibility)
        is_valid, error = self._validate_skill_name(str(name), directory_name)
        if not is_valid:
            logger.warning(
                "Skill '%s' in %s does not follow Agent Skills specification: %s. Consider renaming for spec compliance.",
                name,
                skill_path,
                error,
            )

        # Validate description length per spec (max 1024 chars)
        description_str = str(description).strip()
        if len(description_str) > MAX_SKILL_DESCRIPTION_LENGTH:
            logger.warning(
                "Description exceeds %d characters in %s, truncating",
                MAX_SKILL_DESCRIPTION_LENGTH,
                skill_path,
            )
            description_str = description_str[:MAX_SKILL_DESCRIPTION_LENGTH]

        if frontmatter_data.get("allowed-tools"):
            allowed_tools = cast(str, frontmatter_data.get("allowed-tools")).split(" ")
        else:
            allowed_tools = []

        return SkillMetadata(
            name=str(name),
            description=description_str,
            path=skill_path,
            metadata=frontmatter_data.get("metadata", {}),
            license=frontmatter_data.get("license", "").strip() or None,
            compatibility=frontmatter_data.get("compatibility", "").strip() or None,
            allowed_tools=allowed_tools,
        )

    def _format_skills_list(self, skills: list[SkillMetadata]) -> str:
        """Format skills metadata for display in system prompt."""
        if not skills:
            return f"(No skills available yet. You can create skills in {self.skill_template_dir})"

        lines = []
        for skill in skills:
            lines.append(f"- **{skill.name}**: {skill.description}")
            lines.append(f"  -> Read `{skill.path}` for full instructions")

        return "\n".join(lines)
