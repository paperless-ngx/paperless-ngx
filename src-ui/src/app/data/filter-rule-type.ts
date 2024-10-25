import { DataType } from './datatype'

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

export const FILTER_CUSTOM_FIELDS_TEXT = 36
export const FILTER_HAS_CUSTOM_FIELDS_ALL = 38
export const FILTER_HAS_CUSTOM_FIELDS_ANY = 39
export const FILTER_DOES_NOT_HAVE_CUSTOM_FIELDS = 40
export const FILTER_HAS_ANY_CUSTOM_FIELDS = 41

export const FILTER_CUSTOM_FIELDS_QUERY = 42

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
    datatype: DataType.Correspondent,
    multi: false,
  },
  {
    id: FILTER_HAS_CORRESPONDENT_ANY,
    filtervar: 'correspondent__id__in',
    datatype: DataType.Correspondent,
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_CORRESPONDENT,
    filtervar: 'correspondent__id__none',
    datatype: DataType.Correspondent,
    multi: true,
  },
  {
    id: FILTER_STORAGE_PATH,
    filtervar: 'storage_path__id',
    isnull_filtervar: 'storage_path__isnull',
    datatype: DataType.StoragePath,
    multi: false,
  },
  {
    id: FILTER_HAS_STORAGE_PATH_ANY,
    filtervar: 'storage_path__id__in',
    datatype: DataType.StoragePath,
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_STORAGE_PATH,
    filtervar: 'storage_path__id__none',
    datatype: DataType.StoragePath,
    multi: true,
  },
  {
    id: FILTER_DOCUMENT_TYPE,
    filtervar: 'document_type__id',
    isnull_filtervar: 'document_type__isnull',
    datatype: DataType.DocumentType,
    multi: false,
  },
  {
    id: FILTER_HAS_DOCUMENT_TYPE_ANY,
    filtervar: 'document_type__id__in',
    datatype: DataType.DocumentType,
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_DOCUMENT_TYPE,
    filtervar: 'document_type__id__none',
    datatype: DataType.DocumentType,
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
    datatype: DataType.Tag,
    multi: true,
  },
  {
    id: FILTER_HAS_TAGS_ANY,
    filtervar: 'tags__id__in',
    datatype: DataType.Tag,
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_TAG,
    filtervar: 'tags__id__none',
    datatype: DataType.Tag,
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
    filtervar: 'created__date__lt',
    datatype: 'date',
    multi: false,
  },
  {
    id: FILTER_CREATED_AFTER,
    filtervar: 'created__date__gt',
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
    filtervar: 'added__date__lt',
    datatype: 'date',
    multi: false,
  },
  {
    id: FILTER_ADDED_AFTER,
    filtervar: 'added__date__gt',
    datatype: 'date',
    multi: false,
  },
  {
    id: FILTER_MODIFIED_BEFORE,
    filtervar: 'modified__date__lt',
    datatype: 'date',
    multi: false,
  },
  {
    id: FILTER_MODIFIED_AFTER,
    filtervar: 'modified__date__gt',
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
    id: FILTER_CUSTOM_FIELDS_TEXT,
    filtervar: 'custom_fields__icontains',
    datatype: 'string',
    multi: false,
  },
  {
    id: FILTER_HAS_CUSTOM_FIELDS_ALL,
    filtervar: 'custom_fields__id__all',
    datatype: 'number',
    multi: true,
  },
  {
    id: FILTER_HAS_CUSTOM_FIELDS_ANY,
    filtervar: 'custom_fields__id__in',
    datatype: 'number',
    multi: true,
  },
  {
    id: FILTER_DOES_NOT_HAVE_CUSTOM_FIELDS,
    filtervar: 'custom_fields__id__none',
    datatype: 'number',
    multi: true,
  },
  {
    id: FILTER_HAS_ANY_CUSTOM_FIELDS,
    filtervar: 'has_custom_fields',
    datatype: 'boolean',
    multi: false,
    default: true,
  },
  {
    id: FILTER_CUSTOM_FIELDS_QUERY,
    filtervar: 'custom_field_query',
    datatype: 'string',
    multi: false,
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
