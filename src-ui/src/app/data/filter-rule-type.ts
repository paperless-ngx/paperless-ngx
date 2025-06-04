// These correspond to src/documents/models.py and changes here require a DB migration (and vice versa)
export const FILTER_TITLE = 0
export const FILTER_CONTENT = 1

export const FILTER_ASN = 2
export const FILTER_ASN_ISNULL = 18
export const FILTER_ASN_GT = 23
export const FILTER_ASN_LT = 24

export const FILTER_CORRESPONDENT = 3
export const FILTER_HAS_CORRESPONDENT_ANY = 26
export const FILTER_DOES_NOT_HAVE_CORRESPONDENT = 27

export const FILTER_DOCUMENT_TYPE = 4
export const FILTER_HAS_DOCUMENT_TYPE_ANY = 28
export const FILTER_DOES_NOT_HAVE_DOCUMENT_TYPE = 29

export const FILTER_IS_IN_INBOX = 5
export const FILTER_HAS_TAGS_ALL = 6
export const FILTER_HAS_ANY_TAG = 7
export const FILTER_DOES_NOT_HAVE_TAG = 17
export const FILTER_HAS_TAGS_ANY = 22

export const FILTER_STORAGE_PATH = 25
export const FILTER_HAS_STORAGE_PATH_ANY = 30
export const FILTER_DOES_NOT_HAVE_STORAGE_PATH = 31

export const FILTER_CREATED_BEFORE = 8
export const FILTER_CREATED_AFTER = 9
export const FILTER_CREATED_YEAR = 10
export const FILTER_CREATED_MONTH = 11
export const FILTER_CREATED_DAY = 12

export const FILTER_ADDED_BEFORE = 13
export const FILTER_ADDED_AFTER = 14

export const FILTER_MODIFIED_BEFORE = 15
export const FILTER_MODIFIED_AFTER = 16

export const FILTER_TITLE_CONTENT = 19
export const FILTER_FULLTEXT_QUERY = 20
export const FILTER_FULLTEXT_MORELIKE = 21

export const FILTER_OWNER = 32
export const FILTER_OWNER_ANY = 33
export const FILTER_OWNER_ISNULL = 34
export const FILTER_OWNER_DOES_NOT_INCLUDE = 35
export const FILTER_SHARED_BY_USER = 37

export const FILTER_CUSTOM_FIELDS = 36

export const FILTER_WAREHOUSE = 53
export const FILTER_HAS_WAREHOUSE_ANY = 54
export const FILTER_DOES_NOT_HAVE_WAREHOUSE = 55

//Box
export const FILTER_BOX = 56
export const FILTER_HAS_BOX_ANY = 57
export const FILTER_DOES_NOT_HAVE_BOX = 58

//export const Shelf= 36
export const FILTER_CUSTOM_SHELF = 59
export const FILTER_HAS_CUSTOM_SHELF_ANY = 60
export const FILTER_DOES_NOT_HAVE_CUSTOM_SHELF = 61

export const FILTER_FOLDER = 62
export const FILTER_HAS_FOLDER_ANY = 63
export const FILTER_DOES_NOT_HAVE_FOLDER = 64
export const FILTER_HAS_FOLDER_ALL = 65

export const FILTER_DOSSIER = 66
export const FILTER_HAS_DOSSIER_ANY = 67
export const FILTER_DOES_NOT_HAVE_DOSSIER = 68
export const FILTER_HAS_DOSSIER_ALL = 69

export const FILTER_ARCHIVE_FONT = 70
export const FILTER_HAS_ARCHIVE_FONT_ANY = 71
export const FILTER_DOES_NOT_HAVE_ARCHIVE_FONT = 72

export const FILTER_FONT_LANGUAGE = 73
export const FILTER_HAS_FONT_LANGUAGE_ANY = 74
export const FILTER_DOES_NOT_HAVE_FONT_LANGUAGE = 75

export const FILTER_RULE_TYPES: FilterRuleType[] = [
  {
    id: FILTER_TITLE,
    filtervar: 'title__icontains',
    datatype: 'string',
    multi: false,
    default: '',
  },
  {
    id: FILTER_CONTENT,
    filtervar: 'content__icontains',
    datatype: 'string',
    multi: false,
    default: '',
  },
  {
    id: FILTER_ASN,
    filtervar: 'archive_serial_number',
    datatype: 'number',
    multi: false,
  },
  {
    id: FILTER_CORRESPONDENT,
    filtervar: 'correspondent__id',
    isnull_filtervar: 'correspondent__isnull',
    datatype: 'correspondent',
    multi: false,
  },
  {
    id: FILTER_HAS_CORRESPONDENT_ANY,
    filtervar: 'correspondent__id__in',
    datatype: 'correspondent',
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_CORRESPONDENT,
    filtervar: 'correspondent__id__none',
    datatype: 'correspondent',
    multi: true,
  },
  {
    id: FILTER_STORAGE_PATH,
    filtervar: 'storage_path__id',
    isnull_filtervar: 'storage_path__isnull',
    datatype: 'storage_path',
    multi: false,
  },
  {
    id: FILTER_HAS_STORAGE_PATH_ANY,
    filtervar: 'storage_path__id__in',
    datatype: 'storage_path',
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_STORAGE_PATH,
    filtervar: 'storage_path__id__none',
    datatype: 'storage_path',
    multi: true,
  },
  {
    id: FILTER_WAREHOUSE,
    filtervar: 'warehouse_w__id',
    isnull_filtervar: 'warehouse_w__isnull',
    datatype: 'warehouse',
    multi: false,
  },
  {
    id: FILTER_HAS_WAREHOUSE_ANY,
    filtervar: 'warehouse_w__id__in',
    datatype: 'warehouse',
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_WAREHOUSE,
    filtervar: 'warehouse_w__id__none',
    datatype: 'warehouse',
    multi: true,
  },
  {
    id: FILTER_HAS_FOLDER_ALL,
    filtervar: 'folders__id__all',
    datatype: 'folder',
    multi: true,
  },
  {
    id: FILTER_FOLDER,
    filtervar: 'folder__id',
    isnull_filtervar: 'folder__isnull',
    datatype: 'folder',
    multi: false,
  },
  {
    id: FILTER_HAS_FOLDER_ANY,
    filtervar: 'folder__id__in',
    datatype: 'folder',
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_FOLDER,
    filtervar: 'folder__id__none',
    datatype: 'folder',
    multi: true,
  },
  //box
  {
    id: FILTER_BOX,
    filtervar: 'warehouse__id',
    isnull_filtervar: 'warehouse__isnull',
    datatype: 'warehouse',
    multi: false,
  },
  {
    id: FILTER_HAS_BOX_ANY,
    filtervar: 'warehouse__id__in',
    datatype: 'warehouse',
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_BOX,
    filtervar: 'warehouse__id__none',
    datatype: 'warehouse',
    multi: true,
  },
  //Shelf
  {
    id: FILTER_CUSTOM_SHELF,
    filtervar: 'warehouse_s__id',
    isnull_filtervar: 'warehouse_s__isnull',
    datatype: 'warehouse',
    multi: false,
  },
  {
    id: FILTER_HAS_CUSTOM_SHELF_ANY,
    filtervar: 'warehouse_s__id__in',
    datatype: 'warehouse',
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_CUSTOM_SHELF,
    filtervar: 'warehouse_s__id__none',
    datatype: 'warehouse',
    multi: true,
  },

  {
    id: FILTER_DOCUMENT_TYPE,
    filtervar: 'document_type__id',
    isnull_filtervar: 'document_type__isnull',
    datatype: 'document_type',
    multi: false,
  },
  {
    id: FILTER_HAS_DOCUMENT_TYPE_ANY,
    filtervar: 'document_type__id__in',
    datatype: 'document_type',
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_DOCUMENT_TYPE,
    filtervar: 'document_type__id__none',
    datatype: 'document_type',
    multi: true,
  },
  {
    id: FILTER_IS_IN_INBOX,
    filtervar: 'is_in_inbox',
    datatype: 'boolean',
    multi: false,
    default: true,
  },
  {
    id: FILTER_HAS_TAGS_ALL,
    filtervar: 'tags__id__all',
    datatype: 'tag',
    multi: true,
  },
  {
    id: FILTER_HAS_TAGS_ANY,
    filtervar: 'tags__id__in',
    datatype: 'tag',
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_TAG,
    filtervar: 'tags__id__none',
    datatype: 'tag',
    multi: true,
  },
  {
    id: FILTER_HAS_ANY_TAG,
    filtervar: 'is_tagged',
    datatype: 'boolean',
    multi: false,
    default: true,
  },
  {
    id: FILTER_CREATED_BEFORE,
    filtervar: 'created__date__lte',
    datatype: 'date',
    multi: false,
  },
  {
    id: FILTER_CREATED_AFTER,
    filtervar: 'created__date__gte',
    datatype: 'date',
    multi: false,
  },
  {
    id: FILTER_CREATED_YEAR,
    filtervar: 'created__year',
    datatype: 'number',
    multi: false,
  },
  {
    id: FILTER_CREATED_MONTH,
    filtervar: 'created__month',
    datatype: 'number',
    multi: false,
  },
  {
    id: FILTER_CREATED_DAY,
    filtervar: 'created__day',
    datatype: 'number',
    multi: false,
  },

  {
    id: FILTER_ADDED_BEFORE,
    filtervar: 'added__date__lte',
    datatype: 'date',
    multi: false,
  },
  {
    id: FILTER_ADDED_AFTER,
    filtervar: 'added__date__gte',
    datatype: 'date',
    multi: false,
  },
  {
    id: FILTER_MODIFIED_BEFORE,
    filtervar: 'modified__date__lte',
    datatype: 'date',
    multi: false,
  },
  {
    id: FILTER_MODIFIED_AFTER,
    filtervar: 'modified__date__gte',
    datatype: 'date',
    multi: false,
  },
  {
    id: FILTER_ASN_ISNULL,
    filtervar: 'archive_serial_number__isnull',
    datatype: 'boolean',
    multi: false,
  },
  {
    id: FILTER_ASN_GT,
    filtervar: 'archive_serial_number__gt',
    datatype: 'number',
    multi: false,
  },
  {
    id: FILTER_ASN_LT,
    filtervar: 'archive_serial_number__lt',
    datatype: 'number',
    multi: false,
  },
  {
    id: FILTER_TITLE_CONTENT,
    filtervar: 'title_content',
    datatype: 'string',
    multi: false,
  },
  {
    id: FILTER_FULLTEXT_QUERY,
    filtervar: 'query',
    datatype: 'string',
    multi: false,
  },
  {
    id: FILTER_FULLTEXT_MORELIKE,
    filtervar: 'more_like_id',
    datatype: 'number',
    multi: false,
  },
  {
    id: FILTER_OWNER,
    filtervar: 'owner__id',
    datatype: 'number',
    multi: false,
  },
  {
    id: FILTER_OWNER_ANY,
    filtervar: 'owner__id__in',
    datatype: 'number',
    multi: true,
  },
  {
    id: FILTER_OWNER_ISNULL,
    filtervar: 'owner__isnull',
    datatype: 'boolean',
    multi: false,
  },
  {
    id: FILTER_OWNER_DOES_NOT_INCLUDE,
    filtervar: 'owner__id__none',
    datatype: 'number',
    multi: true,
  },
  {
    id: FILTER_SHARED_BY_USER,
    filtervar: 'shared_by__id',
    datatype: 'number',
    multi: true,
  },
  {
    id: FILTER_CUSTOM_FIELDS,
    filtervar: 'custom_fields__icontains',
    datatype: 'string',
    multi: false,
  },
  {
    id: FILTER_ARCHIVE_FONT,
    filtervar: 'archive_font__id',
    isnull_filtervar: 'archive_font__isnull',
    datatype: 'archive_font',
    multi: false,
  },
  {
    id: FILTER_HAS_ARCHIVE_FONT_ANY,
    filtervar: 'archive_font__id__in',
    datatype: 'archive_font',
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_ARCHIVE_FONT,
    filtervar: 'archive_font__id__none',
    datatype: 'archive_font',
    multi: true,
  },
  {
    id: FILTER_FONT_LANGUAGE,
    filtervar: 'font_language__id',
    isnull_filtervar: 'font_language__isnull',
    datatype: 'font_language',
    multi: false,
  },
  {
    id: FILTER_HAS_FONT_LANGUAGE_ANY,
    filtervar: 'font_language__id__in',
    datatype: 'font_language',
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_FONT_LANGUAGE,
    filtervar: 'font_language__id__none',
    datatype: 'font_language',
    multi: true,
  },
]

export interface FilterRuleType {
  id: number
  filtervar: string
  isnull_filtervar?: string
  datatype: string //number, string, boolean, date
  multi: boolean
  default?: any
}
