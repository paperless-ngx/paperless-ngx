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
  value?: string
  valueTo?: string
  unit?: AdvancedSearchDateUnit // for WithinLast
}

export interface AdvancedSearchQueryGroup {
  type: AdvancedSearchQueryElementType.Group
  operator: AdvancedSearchLogicalOperator
  children: AdvancedSearchQueryElement[]
}

export type AdvancedSearchQueryElement =
  AdvancedSearchQueryAtom | AdvancedSearchQueryGroup

export const ADVANCED_SEARCH_MAX_DEPTH = 2
export const ADVANCED_SEARCH_MAX_ATOMS = 10

export const ADVANCED_SEARCH_FIELD_LABELS: Record<AdvancedSearchField, string> =
  {
    [AdvancedSearchField.Any]: $localize`Any field`,
    [AdvancedSearchField.Title]: $localize`Title`,
    [AdvancedSearchField.Content]: $localize`Content`,
    [AdvancedSearchField.OriginalFilename]: $localize`File name`,
    [AdvancedSearchField.NoteText]: $localize`Note text`,
    [AdvancedSearchField.NoteAuthor]: $localize`Note author`,
    [AdvancedSearchField.CustomFieldName]: $localize`Custom field name`,
    [AdvancedSearchField.CustomFieldValue]: $localize`Custom field value`,
    [AdvancedSearchField.Correspondent]: $localize`Correspondent name`,
    [AdvancedSearchField.DocumentType]: $localize`Document type name`,
    [AdvancedSearchField.StoragePath]: $localize`Storage path name`,
    [AdvancedSearchField.Tag]: $localize`Tag name`,
    [AdvancedSearchField.ASN]: $localize`ASN`,
    [AdvancedSearchField.PageCount]: $localize`Pages`,
    [AdvancedSearchField.NumNotes]: $localize`Number of notes`,
    [AdvancedSearchField.Created]: $localize`Created`,
    [AdvancedSearchField.Added]: $localize`Added`,
    [AdvancedSearchField.Modified]: $localize`Modified`,
    [AdvancedSearchField.Checksum]: $localize`Checksum`,
  }

export const ADVANCED_SEARCH_FIELD_GROUPS: {
  label: string
  fields: AdvancedSearchField[]
}[] = [
  {
    label: $localize`Text`,
    fields: [
      AdvancedSearchField.Any,
      AdvancedSearchField.Title,
      AdvancedSearchField.Content,
      AdvancedSearchField.OriginalFilename,
      AdvancedSearchField.NoteText,
      AdvancedSearchField.NoteAuthor,
      AdvancedSearchField.CustomFieldName,
      AdvancedSearchField.CustomFieldValue,
    ],
  },
  {
    label: $localize`Names`,
    fields: [
      AdvancedSearchField.Correspondent,
      AdvancedSearchField.DocumentType,
      AdvancedSearchField.StoragePath,
      AdvancedSearchField.Tag,
    ],
  },
  {
    label: $localize`Numbers`,
    fields: [
      AdvancedSearchField.ASN,
      AdvancedSearchField.PageCount,
      AdvancedSearchField.NumNotes,
    ],
  },
  {
    label: $localize`Dates`,
    fields: [
      AdvancedSearchField.Created,
      AdvancedSearchField.Added,
      AdvancedSearchField.Modified,
    ],
  },
  { label: $localize`Other`, fields: [AdvancedSearchField.Checksum] },
]

export const ADVANCED_SEARCH_OPERATOR_LABELS: Record<
  AdvancedSearchOperator,
  string
> = {
  [AdvancedSearchOperator.AllWords]: $localize`contains all words`,
  [AdvancedSearchOperator.AnyWord]: $localize`contains any word`,
  [AdvancedSearchOperator.Phrase]: $localize`contains the phrase`,
  [AdvancedSearchOperator.StartsWith]: $localize`starts with`,
  [AdvancedSearchOperator.Equals]: $localize`is`,
  [AdvancedSearchOperator.AtLeast]: $localize`is at least`,
  [AdvancedSearchOperator.AtMost]: $localize`is at most`,
  [AdvancedSearchOperator.Between]: $localize`is between`,
  [AdvancedSearchOperator.DateKeyword]: $localize`is`,
  [AdvancedSearchOperator.WithinLast]: $localize`is within the last`,
}

// Comparing dates reads differently than comparing counts
export const ADVANCED_SEARCH_DATE_OPERATOR_LABELS: Partial<
  Record<AdvancedSearchOperator, string>
> = {
  [AdvancedSearchOperator.AtLeast]: $localize`is on or after`,
  [AdvancedSearchOperator.AtMost]: $localize`is on or before`,
}

export const ADVANCED_SEARCH_DATE_KEYWORD_LABELS: Record<string, string> = {
  today: $localize`today`,
  yesterday: $localize`yesterday`,
  tomorrow: $localize`tomorrow`,
  'previous week': $localize`previous week`,
  'this month': $localize`this month`,
  'previous month': $localize`previous month`,
  'previous quarter': $localize`previous quarter`,
  'this year': $localize`this year`,
  'previous year': $localize`previous year`,
}

export const ADVANCED_SEARCH_DATE_UNIT_LABELS: Record<
  AdvancedSearchDateUnit,
  string
> = {
  [AdvancedSearchDateUnit.Day]: $localize`days`,
  [AdvancedSearchDateUnit.Week]: $localize`weeks`,
  [AdvancedSearchDateUnit.Month]: $localize`months`,
  [AdvancedSearchDateUnit.Year]: $localize`years`,
}
