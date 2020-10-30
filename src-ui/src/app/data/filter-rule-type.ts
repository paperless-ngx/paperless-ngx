export const FILTER_RULE_TYPES: FilterRuleType[] = [
  {name: "Title contains", filtervar: "title__icontains", datatype: "string"},
  {name: "Content contains", filtervar: "content__icontains", datatype: "string"},
  
  {name: "ASN is", filtervar: "archive_serial_number", datatype: "number"},
  
  {name: "Correspondent is", filtervar: "correspondent__id", datatype: "correspondent"},
  {name: "Document type is", filtervar: "document_type__id", datatype: "document_type"},
  {name: "Has tag", filtervar: "tags__id", datatype: "tag"},
  
  {name: "Has any tag", filtervar: "is_tagged", datatype: "boolean"},

  {name: "Date created before", filtervar: "created__date__lt", datatype: "date"},
  {name: "Date created after", filtervar: "created__date__gt", datatype: "date"},

  {name: "Year created is", filtervar: "created__year", datatype: "number"},
  {name: "Month created is", filtervar: "created__month", datatype: "number"},
  {name: "Day created is", filtervar: "created__day", datatype: "number"},

  {name: "Date added before", filtervar: "added__date__lt", datatype: "date"},
  {name: "Date added after", filtervar: "added__date__gt", datatype: "date"},
  
  {name: "Date modified before", filtervar: "modified__date__lt", datatype: "date"},
  {name: "Date modified after", filtervar: "modified__date__gt", datatype: "date"},
]

export interface FilterRuleType {
  name: string
  filtervar: string
  datatype: string //number, string, boolean, date
}