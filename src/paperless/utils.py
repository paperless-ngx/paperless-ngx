import logging

from dateparser.languages.loader import LocaleDataLoader

logger = logging.getLogger("paperless.utils")

OCR_TO_DATEPARSER_LANGUAGES = {
    """
    Translation map from languages supported by Tesseract OCR
    to languages supported by dateparser.
    To add a language, make sure it is supported by both libraries.
    The ISO 639-2 will help you link a 3-char to 2-char language code.
    Links:
    - Tesseract languages: https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html
    - Python dateparser languages: https://dateparser.readthedocs.io/en/latest/supported_locales.html
    - ISO 639-2: https://www.loc.gov/standards/iso639-2/php/code_list.php
    """
    # TODO check these Dateparser languages as they are not referenced on the ISO639-2 standard,
    # so we didn't find the equivalent in Tesseract:
    # agq, asa, bez, brx, cgg, ckb, dav, dje, dyo, ebu, guz, jgo, jmc, kde, kea, khq, kln,
    # ksb, ksf, ksh, lag, lkt, lrc, luy, mer, mfe, mgh, mgo, mua, mzn, naq, nmg, nnh, nus,
    # rof, rwk, saq, sbp, she, ses, shi, teo, twq, tzm, vun, wae, xog, yav, yue
    "afr": "af",
    "amh": "am",
    "ara": "ar",
    "asm": "as",
    "ast": "ast",
    "aze": "az",
    "bel": "be",
    "bul": "bg",
    "ben": "bn",
    "bod": "bo",
    "bre": "br",
    "bos": "bs",
    "cat": "ca",
    "cher": "chr",
    "ces": "cs",
    "cym": "cy",
    "dan": "da",
    "deu": "de",
    "dzo": "dz",
    "ell": "el",
    "eng": "en",
    "epo": "eo",
    "spa": "es",
    "est": "et",
    "eus": "eu",
    "fas": "fa",
    "fin": "fi",
    "fil": "fil",
    "fao": "fo",  # codespell:ignore
    "fra": "fr",
    "fry": "fy",
    "gle": "ga",
    "gla": "gd",
    "glg": "gl",
    "guj": "gu",
    "heb": "he",
    "hin": "hi",
    "hrv": "hr",
    "hun": "hu",
    "hye": "hy",
    "ind": "id",
    "isl": "is",
    "ita": "it",
    "jpn": "ja",
    "kat": "ka",
    "kaz": "kk",
    "khm": "km",
    "knda": "kn",
    "kor": "ko",
    "kir": "ky",
    "ltz": "lb",
    "lao": "lo",
    "lit": "lt",
    "lav": "lv",
    "mal": "ml",
    "mon": "mn",
    "mar": "mr",
    "msa": "ms",
    "mlt": "mt",
    "mya": "my",
    "nep": "ne",
    "nld": "nl",
    "ori": "or",
    "pan": "pa",
    "pol": "pl",
    "pus": "ps",
    "por": "pt",
    "que": "qu",
    "ron": "ro",
    "rus": "ru",
    "sin": "si",
    "slk": "sk",
    "slv": "sl",
    "sqi": "sq",
    "srp": "sr",
    "swe": "sv",
    "swa": "sw",
    "tam": "ta",
    "tel": "te",  # codespell:ignore
    "tha": "th",  # codespell:ignore
    "tir": "ti",
    "tgl": "tl",
    "ton": "to",
    "tur": "tr",
    "uig": "ug",
    "ukr": "uk",
    "urd": "ur",
    "uzb": "uz",
    "via": "vi",
    "yid": "yi",
    "yor": "yo",
    "chi": "zh",
}


def ocr_to_dateparser_languages(ocr_languages: str) -> list[str]:
    """
    Convert Tesseract OCR_LANGUAGE codes (ISO 639-2, e.g. "eng+fra", with optional scripts like "aze_Cyrl")
    into a list of locales compatible with the `dateparser` library.

    - If a script is provided (e.g., "aze_Cyrl"), attempts to use the full locale (e.g., "az-Cyrl").
    Falls back to the base language (e.g., "az") if needed.
    - If a language cannot be mapped or validated, it is skipped with a warning.
    - Returns a list of valid locales, or an empty list if none could be converted.
    """
    loader = LocaleDataLoader()
    result = []
    try:
        for ocr_language in ocr_languages.split("+"):
            # Split into language and optional script
            ocr_lang_part, *script = ocr_language.split("_")
            ocr_script_part = script[0] if script else None

            language_part = OCR_TO_DATEPARSER_LANGUAGES.get(ocr_lang_part)
            if language_part is None:
                logger.debug(
                    f'Unable to map OCR language "{ocr_lang_part}" to dateparser locale. ',
                )
                continue

            # Ensure base language is supported by dateparser
            loader.get_locale_map(locales=[language_part])

            # Try to add the script part if it's supported by dateparser
            if ocr_script_part:
                dateparser_language = f"{language_part}-{ocr_script_part.title()}"
                try:
                    loader.get_locale_map(locales=[dateparser_language])
                except Exception:
                    logger.info(
                        f"Language variant '{dateparser_language}' not supported by dateparser; falling back to base language '{language_part}'. You can manually set PAPERLESS_DATE_PARSER_LANGUAGES if needed.",
                    )
                    dateparser_language = language_part
            else:
                dateparser_language = language_part
            if dateparser_language not in result:
                result.append(dateparser_language)
    except Exception as e:
        logger.warning(
            f"Error auto-configuring dateparser languages. Set PAPERLESS_DATE_PARSER_LANGUAGES parameter to avoid this. Detail: {e}",
        )
        return []
    if not result:
        logger.info(
            "Unable to automatically determine dateparser languages from OCR_LANGUAGE, falling back to multi-language support.",
        )
    return result
