export const FILTER_RULE_TYPES: FilterRuleType[] = [
  {name: "Title contains", filtervar: "title__icontains", datatype: "string", multi: false},
  {name: "Content contains", filtervar: "content__icontains", datatype: "string", multi: false},
  
  {name: "ASN is", filtervar: "archive_serial_number", datatype: "number", multi: false},
  
  {name: "Correspondent is", filtervar: "correspondent__id", datatype: "correspondent", multi: false},
  {name: "Document type is", filtervar: "document_type__id", datatype: "document_type", multi: false},

  {name: "Is in Inbox", filtervar: "is_in_inbox", datatype: "boolean", multi: false},  
  {name: "Has tag", filtervar: "tags__id__all", datatype: "tag", multi: true},  
  {name: "Has any tag", filtervar: "is_tagged", datatype: "boolean", multi: false},

  {name: "Created before", filtervar: "created__date__lt", datatype: "date", multi: false},
  {name: "Created after", filtervar: "created__date__gt", datatype: "date", multi: false},

  {name: "Year created is", filtervar: "created__year", datatype: "number", multi: false},
  {name: "Month created is", filtervar: "created__month", datatype: "number", multi: false},
  {name: "Day created is", filtervar: "created__day", datatype: "number", multi: false},

  {name: "Added before", filtervar: "added__date__lt", datatype: "date", multi: false},
  {name: "Added after", filtervar: "added__date__gt", datatype: "date", multi: false},
  
  {name: "Modified before", filtervar: "modified__date__lt", datatype: "date", multi: false},
  {name: "Modified after", filtervar: "modified__date__gt", datatype: "date", multi: false},
]

export interface FilterRuleType {
  name: string
  filtervar: string
  datatype: string //number, string, boolean, date
  multi: boolean
}