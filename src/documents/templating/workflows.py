import re
from datetime import date
from datetime import datetime
from pathlib import Path


def parse_w_workflow_placeholders(
    text: str,
    correspondent_name: str,
    doc_type_name: str,
    owner_username: str,
    local_added: datetime,
    original_filename: str,
    filename: str,
    created: date | None = None,
    doc_title: str | None = None,
    doc_url: str | None = None,
    content: str | None = None,
) -> str:
    """
    Available title placeholders for Workflows depend on what has already been assigned,
    e.g. for pre-consumption triggers created will not have been parsed yet, but it will
    for added / updated triggers.
    
    Enhanced to support regex transformations with syntax:
    - {field_name} - simple field replacement (backward compatible)
    - {field_name:s/pattern/replacement/} - regex replacement
    - {field_name:s/pattern/replacement/flags} - regex replacement with flags (i=case insensitive, s=dotall)
    """
    formatting = {
        "correspondent": correspondent_name,
        "document_type": doc_type_name,
        "added": local_added.isoformat(),
        "added_year": local_added.strftime("%Y"),
        "added_year_short": local_added.strftime("%y"),
        "added_month": local_added.strftime("%m"),
        "added_month_name": local_added.strftime("%B"),
        "added_month_name_short": local_added.strftime("%b"),
        "added_day": local_added.strftime("%d"),
        "added_time": local_added.strftime("%H:%M"),
        "owner_username": owner_username,
        "original_filename": Path(original_filename).stem,
        "filename": Path(filename).stem,
        "content": content or "",
    }
    if created is not None:
        formatting.update(
            {
                "created": created.isoformat(),
                "created_year": created.strftime("%Y"),
                "created_year_short": created.strftime("%y"),
                "created_month": created.strftime("%m"),
                "created_month_name": created.strftime("%B"),
                "created_month_name_short": created.strftime("%b"),
                "created_day": created.strftime("%d"),
                "created_time": created.strftime("%H:%M"),
            },
        )
    if doc_title is not None:
        formatting.update({"doc_title": doc_title})
    if doc_url is not None:
        formatting.update({"doc_url": doc_url})
    
    # Handle enhanced placeholders by pre-processing the text
    def replace_placeholder(match):
        """Replace a single placeholder match with its processed value."""
        placeholder_content = match.group(1)  # Content inside the braces
        
        # Use a comprehensive regex to parse enhanced placeholder syntax
        # Pattern: field_name:s/pattern/replacement/flags (flags optional, trailing slash optional)
        # Supports escaped slashes in pattern/replacement
        regex_match = re.match(r'^([^:]+):\s*s/((?:[^/\\]|\\.)*)/((?:[^/\\]|\\.)*)(?:/([is]*))?/?$', placeholder_content)
        
        if regex_match:
            field_name = regex_match.group(1)
            pattern = regex_match.group(2)
            replacement = regex_match.group(3)
            flags_str = regex_match.group(4) or ''
            
            # Convert flags string to re flags
            flags = 0
            if 'i' in flags_str:
                flags |= re.IGNORECASE
            if 's' in flags_str:
                flags |= re.DOTALL
            
            # Get the original value
            original_value = formatting.get(field_name, '')
            if isinstance(original_value, str):
                try:
                    # Convert sed-style backreferences ($1, $2) to Python style (\1, \2)
                    python_replacement = re.sub(r'\$(\d+)', r'\\\1', replacement)
                    
                    # Perform regex substitution (Python's re.sub is global by default)
                    return re.sub(pattern, python_replacement, original_value, flags=flags)
                except re.error:
                    # Fall back to original value for invalid regex
                    return original_value
                except Exception:
                    # Catch any other unexpected errors
                    return original_value
            else:
                # Non-string values can't be regex processed
                return str(original_value) if original_value is not None else ''
        
        # Fallback to original field value (backward compatibility)
        field_name = placeholder_content.split(':')[0]
        return str(formatting.get(field_name, ''))
    
    try:
        # Find all placeholders and replace them
        processed_text = re.sub(r'\{([^}]+)\}', replace_placeholder, text)
        return processed_text.strip()
    except Exception:
        # Fall back to original behavior for malformed placeholders
        return text.strip()
