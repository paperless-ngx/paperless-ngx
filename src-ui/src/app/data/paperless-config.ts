import { ObjectWithId } from './object-with-id'

// see /src/paperless/models.py

export enum OutputTypeConfig {
  PDF = 'pdf',
  PDF_A = 'pdfa',
  PDF_A1 = 'pdfa-1',
  PDF_A2 = 'pdfa-2',
  PDF_A3 = 'pdfa-3',
}

export enum ModeConfig {
  SKIP = 'skip',
  REDO = 'redo',
  FORCE = 'force',
  SKIP_NO_ARCHIVE = 'skip_noarchive',
}

export enum ArchiveFileConfig {
  NEVER = 'never',
  WITH_TEXT = 'with_text',
  ALWAYS = 'always',
}

export enum CleanConfig {
  CLEAN = 'clean',
  FINAL = 'clean-final',
  NONE = 'none',
}

export enum ColorConvertConfig {
  UNCHANGED = 'LeaveColorUnchanged',
  RGB = 'RGB',
  INDEPENDENT = 'UseDeviceIndependentColor',
  GRAY = 'Gray',
  CMYK = 'CMYK',
}

export enum ConfigOptionType {
  String = 'string',
  Number = 'number',
  Select = 'select',
  Boolean = 'boolean',
  JSON = 'json',
  File = 'file',
}

export const ConfigCategory = {
  General: $localize`General Settings`,
  OCR: $localize`OCR Settings`,
}

export interface ConfigOption {
  key: string
  title: string
  type: ConfigOptionType
  choices?: Array<{ id: string; name: string }>
  config_key?: string
  category: string
}

function mapToItems(enumObj: Object): Array<{ id: string; name: string }> {
  return Object.keys(enumObj).map((key) => {
    return {
      id: enumObj[key],
      name: enumObj[key],
    }
  })
}

export const PaperlessConfigOptions: ConfigOption[] = [
  {
    key: 'output_type',
    title: $localize`Output Type`,
    type: ConfigOptionType.Select,
    choices: mapToItems(OutputTypeConfig),
    config_key: 'PAPERLESS_OCR_OUTPUT_TYPE',
    category: ConfigCategory.OCR,
  },
  {
    key: 'language',
    title: $localize`Language`,
    type: ConfigOptionType.String,
    config_key: 'PAPERLESS_OCR_LANGUAGE',
    category: ConfigCategory.OCR,
  },
  {
    key: 'pages',
    title: $localize`Pages`,
    type: ConfigOptionType.Number,
    config_key: 'PAPERLESS_OCR_PAGES',
    category: ConfigCategory.OCR,
  },
  {
    key: 'mode',
    title: $localize`Mode`,
    type: ConfigOptionType.Select,
    choices: mapToItems(ModeConfig),
    config_key: 'PAPERLESS_OCR_MODE',
    category: ConfigCategory.OCR,
  },
  {
    key: 'skip_archive_file',
    title: $localize`Skip Archive File`,
    type: ConfigOptionType.Select,
    choices: mapToItems(ArchiveFileConfig),
    config_key: 'PAPERLESS_OCR_SKIP_ARCHIVE_FILE',
    category: ConfigCategory.OCR,
  },
  {
    key: 'image_dpi',
    title: $localize`Image DPI`,
    type: ConfigOptionType.Number,
    config_key: 'PAPERLESS_OCR_IMAGE_DPI',
    category: ConfigCategory.OCR,
  },
  {
    key: 'unpaper_clean',
    title: $localize`Clean`,
    type: ConfigOptionType.Select,
    choices: mapToItems(CleanConfig),
    config_key: 'PAPERLESS_OCR_CLEAN',
    category: ConfigCategory.OCR,
  },
  {
    key: 'deskew',
    title: $localize`Deskew`,
    type: ConfigOptionType.Boolean,
    config_key: 'PAPERLESS_OCR_DESKEW',
    category: ConfigCategory.OCR,
  },
  {
    key: 'rotate_pages',
    title: $localize`Rotate Pages`,
    type: ConfigOptionType.Boolean,
    config_key: 'PAPERLESS_OCR_ROTATE_PAGES',
    category: ConfigCategory.OCR,
  },
  {
    key: 'rotate_pages_threshold',
    title: $localize`Rotate Pages Threshold`,
    type: ConfigOptionType.Number,
    config_key: 'PAPERLESS_OCR_ROTATE_PAGES_THRESHOLD',
    category: ConfigCategory.OCR,
  },
  {
    key: 'max_image_pixels',
    title: $localize`Max Image Pixels`,
    type: ConfigOptionType.Number,
    config_key: 'PAPERLESS_OCR_MAX_IMAGE_PIXELS',
    category: ConfigCategory.OCR,
  },
  {
    key: 'color_conversion_strategy',
    title: $localize`Color Conversion Strategy`,
    type: ConfigOptionType.Select,
    choices: mapToItems(ColorConvertConfig),
    config_key: 'PAPERLESS_OCR_COLOR_CONVERSION_STRATEGY',
    category: ConfigCategory.OCR,
  },
  {
    key: 'user_args',
    title: $localize`OCR Arguments`,
    type: ConfigOptionType.JSON,
    config_key: 'PAPERLESS_OCR_USER_ARGS',
    category: ConfigCategory.OCR,
  },
  {
    key: 'app_logo',
    title: $localize`Application Logo`,
    type: ConfigOptionType.File,
    config_key: 'PAPERLESS_APP_LOGO',
    category: ConfigCategory.General,
  },
  {
    key: 'app_title',
    title: $localize`Application Title`,
    type: ConfigOptionType.String,
    config_key: 'PAPERLESS_APP_TITLE',
    category: ConfigCategory.General,
  },
]

export interface PaperlessConfig extends ObjectWithId {
  output_type: OutputTypeConfig
  pages: number
  language: string
  mode: ModeConfig
  skip_archive_file: ArchiveFileConfig
  image_dpi: number
  unpaper_clean: CleanConfig
  deskew: boolean
  rotate_pages: boolean
  rotate_pages_threshold: number
  max_image_pixels: number
  color_conversion_strategy: ColorConvertConfig
  user_args: object
  app_logo: string
  app_title: string
}
