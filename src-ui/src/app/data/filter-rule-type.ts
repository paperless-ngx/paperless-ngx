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

export const FILTER_RULE_TYPES: FilterRuleType[] = [

  {id: FILTER_TITLE, name: "Title contains", filtervar: "title__icontains", datatype: "string", multi: false, default: ""},
  {id: FILTER_CONTENT, name: "Content contains", filtervar: "content__icontains", datatype: "string", multi: false, default: ""},

  {id: FILTER_ASN, name: "ASN is", filtervar: "archive_serial_number", datatype: "number", multi: false},

  {id: FILTER_CORRESPONDENT, name: "Correspondent is", displayName: "Correspondents", filtervar: "correspondent__id", datatype: "correspondent", multi: false},
  {id: FILTER_DOCUMENT_TYPE, name: "Document type is", displayName: "Document types", filtervar: "document_type__id", datatype: "document_type", multi: false},

  {id: FILTER_IS_IN_INBOX, name: "Is in Inbox", filtervar: "is_in_inbox", datatype: "boolean", multi: false, default: true},
  {id: FILTER_HAS_TAG, name: "Has tag", displayName: "Tags", filtervar: "tags__id__all", datatype: "tag", multi: true},
  {id: FILTER_DOES_NOT_HAVE_TAG, name: "Does not have tag", filtervar: "tags__id__none", datatype: "tag", multi: true},
  {id: FILTER_HAS_ANY_TAG, name: "Has any tag", filtervar: "is_tagged", datatype: "boolean", multi: false, default: true},

  {id: FILTER_CREATED_BEFORE, name: "Created before", displayName: "Created", filtervar: "created__date__lt", datatype: "date", multi: false},
  {id: FILTER_CREATED_AFTER, name: "Created after", displayName: "Created", filtervar: "created__date__gt", datatype: "date", multi: false},

  {id: FILTER_CREATED_YEAR, name: "Year created is", filtervar: "created__year", datatype: "number", multi: false},
  {id: FILTER_CREATED_MONTH, name: "Month created is", filtervar: "created__month", datatype: "number", multi: false},
  {id: FILTER_CREATED_DAY, name: "Day created is", filtervar: "created__day", datatype: "number", multi: false},

  {id: FILTER_ADDED_BEFORE, name: "Added before", displayName: "Added", filtervar: "added__date__lt", datatype: "date", multi: false},
  {id: FILTER_ADDED_AFTER, name: "Added after", displayName: "Added", filtervar: "added__date__gt", datatype: "date", multi: false},

  {id: FILTER_MODIFIED_BEFORE, name: "Modified before", filtervar: "modified__date__lt", datatype: "date", multi: false},
  {id: FILTER_MODIFIED_AFTER, name: "Modified after", filtervar: "modified__date__gt", datatype: "date", multi: false},
]

export interface FilterRuleType {
  id: number
  name: string
  filtervar: string
  datatype: string //number, string, boolean, date
  multi: boolean
  displayName?: string
  default?: any
}
