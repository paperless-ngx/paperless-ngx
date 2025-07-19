import logging
import re
from datetime import date
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("paperless.templating.workflows")


def _parse_enhanced_placeholder(placeholder_content: str, formatting: dict) -> str:
    """
    Parse enhanced placeholder syntax with regex transformations.
    
    Supports:
    - {field_name} - simple field replacement (backward compatible)
    - {field_name:s/pattern/replacement/} - regex replacement
    - {field_name:s/pattern/replacement/flags} - regex replacement with flags
    
    Args:
        placeholder_content: The content inside the {} placeholder
        formatting: Dictionary of available field values
        
    Returns:
        The transformed value or original field value if transformation fails
    """
    # Check if this is a regex transformation placeholder
    if ':s/' in placeholder_content:
        parts = placeholder_content.split(':s/', 1)
        if len(parts) == 2:
            field_name = parts[0]
            regex_part = parts[1]
            
            # Parse the regex pattern: s/pattern/replacement/flags
            if regex_part.count('/') >= 2:
                # Split by '/' but handle the case where there might be more than expected
                pattern_parts = regex_part.split('/')
                if len(pattern_parts) >= 3:
                    pattern = pattern_parts[0]
                    replacement = pattern_parts[1]
                    flags_str = pattern_parts[2] if len(pattern_parts) > 2 else ''
                    
                    # Convert flags string to re flags
                    flags = 0
                    if 'i' in flags_str:
                        flags |= re.IGNORECASE
                    if 'm' in flags_str:
                        flags |= re.MULTILINE
                    if 's' in flags_str:
                        flags |= re.DOTALL
                    
                    # Get the original value
                    original_value = formatting.get(field_name, '')
                    if isinstance(original_value, str):
                        try:
                            # Convert sed-style backreferences ($1, $2) to Python style (\1, \2)
                            python_replacement = replacement
                            # Handle $1, $2, etc. -> \1, \2, etc.
                            import re as regex_re
                            python_replacement = regex_re.sub(r'\$(\d+)', r'\\\1', replacement)
                            
                            # Perform regex substitution
                            return re.sub(pattern, python_replacement, original_value, flags=flags)
                        except re.error as e:
                            # Log error and return original value
                            logger.warning(
                                f"Regex error in placeholder '{{{placeholder_content}}}': {e}. "
                                f"Falling back to original value."
                            )
                            return original_value
                        except Exception as e:
                            # Catch any other unexpected errors
                            logger.warning(
                                f"Unexpected error in placeholder '{{{placeholder_content}}}': {e}. "
                                f"Falling back to original value."
                            )
                            return original_value
                    else:
                        # Non-string values can't be regex processed
                        logger.warning(
                            f"Cannot apply regex transformation to non-string field '{field_name}' "
                            f"in placeholder '{{{placeholder_content}}}'. Falling back to original value."
                        )
                        return str(original_value) if original_value is not None else ''
    
    # Fallback to original field value (backward compatibility)
    field_name = placeholder_content.split(':')[0]
    return formatting.get(field_name, '')


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
) -> str:
    """
    Available title placeholders for Workflows depend on what has already been assigned,
    e.g. for pre-consumption triggers created will not have been parsed yet, but it will
    for added / updated triggers.
    
    Enhanced to support regex transformations with syntax:
    - {field_name} - simple field replacement (backward compatible)
    - {field_name:s/pattern/replacement/} - regex replacement
    - {field_name:s/pattern/replacement/flags} - regex replacement with flags (i=case insensitive, m=multiline, s=dotall)
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
    import re as regex_module
    
    def replace_placeholder(match):
        """Replace a single placeholder match with its processed value."""
        placeholder_content = match.group(1)  # Content inside the braces
        return str(_parse_enhanced_placeholder(placeholder_content, formatting))
    
    try:
        # Find all placeholders and replace them
        processed_text = regex_module.sub(r'\{([^}]+)\}', replace_placeholder, text)
        return processed_text.strip()
    except Exception as e:
        # Fall back to original behavior for malformed placeholders
        logger.warning(f"Error formatting text '{text}': {e}. Falling back to original text.")
        return text.strip()
