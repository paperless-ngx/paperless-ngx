// Fields and forms documented in docs/usage.md > "Document searches"

export enum AdvancedSearchField {
  Any = '',
  Title = 'title',
  Content = 'content',
  OriginalFilename = 'original_filename',
  NoteText = 'notes.note',
  NoteAuthor = 'notes.user',
  CustomFieldName = 'custom_fields.name',
  CustomFieldValue = 'custom_fields.value',
  Correspondent = 'correspondent',
  DocumentType = 'document_type',
  StoragePath = 'storage_path',
  Tag = 'tag',
  ASN = 'asn',
  PageCount = 'page_count',
  NumNotes = 'num_notes',
  Created = 'created',
  Added = 'added',
  Modified = 'modified',
  Checksum = 'checksum',
}

export enum AdvancedSearchFieldKind {
  Text = 'text',
  Number = 'number',
  Date = 'date',
  Checksum = 'checksum',
}

export const ADVANCED_SEARCH_FIELD_KINDS: Record<
  AdvancedSearchField,
  AdvancedSearchFieldKind
> = {
  [AdvancedSearchField.Any]: AdvancedSearchFieldKind.Text,
  [AdvancedSearchField.Title]: AdvancedSearchFieldKind.Text,
  [AdvancedSearchField.Content]: AdvancedSearchFieldKind.Text,
  [AdvancedSearchField.OriginalFilename]: AdvancedSearchFieldKind.Text,
  [AdvancedSearchField.NoteText]: AdvancedSearchFieldKind.Text,
  [AdvancedSearchField.NoteAuthor]: AdvancedSearchFieldKind.Text,
  [AdvancedSearchField.CustomFieldName]: AdvancedSearchFieldKind.Text,
  [AdvancedSearchField.CustomFieldValue]: AdvancedSearchFieldKind.Text,
  [AdvancedSearchField.Correspondent]: AdvancedSearchFieldKind.Text,
  [AdvancedSearchField.DocumentType]: AdvancedSearchFieldKind.Text,
  [AdvancedSearchField.StoragePath]: AdvancedSearchFieldKind.Text,
  [AdvancedSearchField.Tag]: AdvancedSearchFieldKind.Text,
  [AdvancedSearchField.ASN]: AdvancedSearchFieldKind.Number,
  [AdvancedSearchField.PageCount]: AdvancedSearchFieldKind.Number,
  [AdvancedSearchField.NumNotes]: AdvancedSearchFieldKind.Number,
  [AdvancedSearchField.Created]: AdvancedSearchFieldKind.Date,
  [AdvancedSearchField.Added]: AdvancedSearchFieldKind.Date,
  [AdvancedSearchField.Modified]: AdvancedSearchFieldKind.Date,
  [AdvancedSearchField.Checksum]: AdvancedSearchFieldKind.Checksum,
}

export enum AdvancedSearchOperator {
  AllWords = 'all',
  AnyWord = 'any',
  Phrase = 'phrase',
  StartsWith = 'prefix',
  Equals = 'eq',
  AtLeast = 'gte',
  AtMost = 'lte',
  Between = 'between',
  DateKeyword = 'keyword',
  WithinLast = 'within',
}

export const ADVANCED_SEARCH_OPERATORS_BY_KIND: Record<
  AdvancedSearchFieldKind,
  AdvancedSearchOperator[]
> = {
  [AdvancedSearchFieldKind.Text]: [
    AdvancedSearchOperator.AllWords,
    AdvancedSearchOperator.AnyWord,
    AdvancedSearchOperator.Phrase,
    AdvancedSearchOperator.StartsWith,
  ],
  [AdvancedSearchFieldKind.Number]: [
    AdvancedSearchOperator.Equals,
    AdvancedSearchOperator.AtLeast,
    AdvancedSearchOperator.AtMost,
    AdvancedSearchOperator.Between,
  ],
  [AdvancedSearchFieldKind.Date]: [
    AdvancedSearchOperator.DateKeyword,
    AdvancedSearchOperator.WithinLast,
    AdvancedSearchOperator.AtLeast,
    AdvancedSearchOperator.AtMost,
    AdvancedSearchOperator.Between,
  ],
  [AdvancedSearchFieldKind.Checksum]: [AdvancedSearchOperator.StartsWith],
}

export const ADVANCED_SEARCH_DATE_KEYWORDS = [
  'today',
  'yesterday',
  'tomorrow',
  'previous week',
  'this month',
  'previous month',
  'previous quarter',
  'this year',
  'previous year',
] as const

export type AdvancedSearchDateKeyword =
  (typeof ADVANCED_SEARCH_DATE_KEYWORDS)[number]

export enum AdvancedSearchDateUnit {
  Day = 'day',
  Week = 'week',
  Month = 'month',
  Year = 'year',
}

export enum AdvancedSearchLogicalOperator {
  And = 'AND',
  Or = 'OR',
  Not = 'NOT',
}

export enum AdvancedSearchQueryElementType {
  Atom = 'atom',
  Group = 'group',
}

export interface AdvancedSearchQueryAtom {
  type: AdvancedSearchQueryElementType.Atom
  field: AdvancedSearchField
  operator: AdvancedSearchOperator
  // words, phrase, number or yyyy-mm-dd date; the lower bound for Between;
  // the amount for WithinLast
  value?: string
  // upper bound for Between
  valueTo?: string
  // unit for WithinLast
  unit?: AdvancedSearchDateUnit
}

export interface AdvancedSearchQueryGroup {
  type: AdvancedSearchQueryElementType.Group
  operator: AdvancedSearchLogicalOperator
  children: AdvancedSearchQueryElement[]
}

export type AdvancedSearchQueryElement =
  AdvancedSearchQueryAtom | AdvancedSearchQueryGroup
