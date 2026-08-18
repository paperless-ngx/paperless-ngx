import dataclasses
import enum
from typing import ClassVar

from jinja2 import Environment
from jinja2 import PackageLoader
from jinja2 import StrictUndefined


class PromptName(enum.Enum):
    CLASSIFICATION = "classification"
    CLASSIFICATION_RAG_CONTEXT = "classification_rag_context"
    LOCALIZATION = "localization"
    TAXONOMY_BLOCK = "taxonomy_block"
    ASSIGNED_BLOCK = "assigned_block"
    CHAT_QA = "chat_qa"
    CHAT_REFINE = "chat_refine"


@dataclasses.dataclass(frozen=True, slots=True)
class PromptContext:
    template_name: ClassVar[PromptName]


# Every render here goes through Environment.get_template() and
# .render(**dataclasses.asdict(context)). This is variable substitution,
# never a template-source compile. If you're about to call from_string()/Template()
# on anything derived from user input, stop: that needs a sandboxed
# environment (see documents/templating/environment.py), not this one.
_env = Environment(
    loader=PackageLoader("paperless_ai", "prompts"),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
    autoescape=False,
    undefined=StrictUndefined,
)


def render_prompt(context: PromptContext) -> str:
    template = _env.get_template(f"{context.template_name.value}.j2")
    return template.render(**dataclasses.asdict(context)).strip()
