export const FILTER_TITLE = 0
export const FILTER_CONTENT = 1
export const FILTER_ASN = 2
export const FILTER_CORRESPONDENT = 3
export const FILTER_DOCUMENT_TYPE = 4
export const FILTER_IS_IN_INBOX = 5
export const FILTER_HAS_TAG = 6
export const FILTER_HAS_ANY_TAG = 7
export const FILTER_CREATED_BEFORE = 8
export const FILTER_CREATED_AFTER = 9
export const FILTER_CREATED_YEAR = 10
export const FILTER_CREATED_MONTH = 11
export const FILTER_CREATED_DAY = 12
export const FILTER_ADDED_BEFORE = 13
export const FILTER_ADDED_AFTER = 14
export const FILTER_MODIFIED_BEFORE = 15
export const FILTER_MODIFIED_AFTER = 16

export const FILTER_DOES_NOT_HAVE_TAG = 17

export const FILTER_ASN_ISNULL = 18

export const FILTER_TITLE_CONTENT = 19

export const FILTER_FULLTEXT_QUERY = 20
export const FILTER_FULLTEXT_MORELIKE = 21

export const FILTER_RULE_TYPES: FilterRuleType[] = [

  {id: FILTER_TITLE, filtervar: "title__icontains", datatype: "string", multi: false, default: ""},
  {id: FILTER_CONTENT, filtervar: "content__icontains", datatype: "string", multi: false, default: ""},

  {id: FILTER_ASN, filtervar: "archive_serial_number", datatype: "number", multi: false},

  {id: FILTER_CORRESPONDENT, filtervar: "correspondent__id", isnull_filtervar: "correspondent__isnull", datatype: "correspondent", multi: false},
  {id: FILTER_DOCUMENT_TYPE, filtervar: "document_type__id", isnull_filtervar: "document_type__isnull", datatype: "document_type", multi: false},

  {id: FILTER_IS_IN_INBOX, filtervar: "is_in_inbox", datatype: "boolean", multi: false, default: true},
  {id: FILTER_HAS_TAG, filtervar: "tags__id__all", datatype: "tag", multi: true},
  {id: FILTER_DOES_NOT_HAVE_TAG, filtervar: "tags__id__none", datatype: "tag", multi: true},
  {id: FILTER_HAS_ANY_TAG, filtervar: "is_tagged", datatype: "boolean", multi: false, default: true},

  {id: FILTER_CREATED_BEFORE, filtervar: "created__date__lt", datatype: "date", multi: false},
  {id: FILTER_CREATED_AFTER, filtervar: "created__date__gt", datatype: "date", multi: false},

  {id: FILTER_CREATED_YEAR, filtervar: "created__year", datatype: "number", multi: false},
  {id: FILTER_CREATED_MONTH, filtervar: "created__month", datatype: "number", multi: false},
  {id: FILTER_CREATED_DAY, filtervar: "created__day", datatype: "number", multi: false},

  {id: FILTER_ADDED_BEFORE, filtervar: "added__date__lt", datatype: "date", multi: false},
  {id: FILTER_ADDED_AFTER, filtervar: "added__date__gt", datatype: "date", multi: false},

  {id: FILTER_MODIFIED_BEFORE, filtervar: "modified__date__lt", datatype: "date", multi: false},
  {id: FILTER_MODIFIED_AFTER, filtervar: "modified__date__gt", datatype: "date", multi: false},
  {id: FILTER_ASN_ISNULL, filtervar: "archive_serial_number__isnull", datatype: "boolean", multi: false},

  {id: FILTER_TITLE_CONTENT, filtervar: "title_content", datatype: "string", multi: false},

  {id: FILTER_FULLTEXT_QUERY, filtervar: "query", datatype: "string", multi: false},

  {id: FILTER_FULLTEXT_MORELIKE, filtervar: "more_like_id", datatype: "number", multi: false},
]

export interface FilterRuleType {
  id: number
  filtervar: string
  isnull_filtervar?: string
  datatype: string //number, string, boolean, date
  multi: boolean
  default?: any
}
