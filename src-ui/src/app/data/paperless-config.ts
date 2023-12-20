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
}
