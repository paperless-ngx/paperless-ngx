import {
  AdvancedSearchDateUnit,
  AdvancedSearchField,
  AdvancedSearchLogicalOperator,
  AdvancedSearchOperator,
  AdvancedSearchQueryAtom,
  AdvancedSearchQueryElement,
  AdvancedSearchQueryElementType,
  AdvancedSearchQueryGroup,
} from '../data/advanced-search-query'
import { serializeAdvancedSearchQuery } from './advanced-search-query'

const atom = (
  field: AdvancedSearchField,
  operator: AdvancedSearchOperator,
  value?: string,
  extra: Partial<AdvancedSearchQueryAtom> = {}
): AdvancedSearchQueryAtom => ({
  type: AdvancedSearchQueryElementType.Atom,
  field,
  operator,
  value,
  ...extra,
})

const group = (
  operator: AdvancedSearchLogicalOperator,
  ...children: AdvancedSearchQueryElement[]
): AdvancedSearchQueryGroup => ({
  type: AdvancedSearchQueryElementType.Group,
  operator,
  children,
})

const { And, Or, Not } = AdvancedSearchLogicalOperator

describe('serializeAdvancedSearchQuery', () => {
  describe('text fields', () => {
    it.each([
      [AdvancedSearchOperator.AllWords, 'invoice', 'title:invoice'],
      [
        AdvancedSearchOperator.AllWords,
        '  invoice   unpaid ',
        'title:invoice AND title:unpaid',
      ],
      [
        AdvancedSearchOperator.AnyWord,
        'invoice unpaid',
        'title:invoice OR title:unpaid',
      ],
      [
        AdvancedSearchOperator.Phrase,
        'quick brown fox',
        'title:"quick brown fox"',
      ],
      [AdvancedSearchOperator.Phrase, 'say "hi"', 'title:"say hi"'],
      [AdvancedSearchOperator.StartsWith, 'invoi', 'title:invoi*'],
      [AdvancedSearchOperator.StartsWith, 'in*v?oi', 'title:invoi*'],
    ])('%s %j writes %s', (operator, value, expected) => {
      expect(
        serializeAdvancedSearchQuery(
          atom(AdvancedSearchField.Title, operator, value)
        )
      ).toBe(expected)
    })

    it('writes bare words for the Any field', () => {
      expect(
        serializeAdvancedSearchQuery(
          atom(AdvancedSearchField.Any, AdvancedSearchOperator.AllWords, 'a b')
        )
      ).toBe('a AND b')
    })

    it.each([
      ['A-1312/99', 'custom_fields.value:A-1312/99'],
      ["O'Brien", "custom_fields.value:O'Brien"],
      ["'quoted'", `custom_fields.value:"'quoted'"`],
      ['foo:bar', 'custom_fields.value:"foo:bar"'],
      ['(x)', 'custom_fields.value:"(x)"'],
      ['2024*', 'custom_fields.value:"2024*"'],
      ['a,b', 'custom_fields.value:"a,b"'],
      ['OR', 'custom_fields.value:"OR"'],
      ['or', 'custom_fields.value:or'],
    ])(
      'quotes %j only when the grammar would read it as syntax',
      (value, expected) => {
        expect(
          serializeAdvancedSearchQuery(
            atom(
              AdvancedSearchField.CustomFieldValue,
              AdvancedSearchOperator.AllWords,
              value
            )
          )
        ).toBe(expected)
      }
    )

    it('uses the dotted names for custom fields', () => {
      expect(
        serializeAdvancedSearchQuery(
          group(
            And,
            atom(
              AdvancedSearchField.CustomFieldName,
              AdvancedSearchOperator.Phrase,
              'status'
            ),
            atom(
              AdvancedSearchField.CustomFieldValue,
              AdvancedSearchOperator.AllWords,
              'paid'
            )
          )
        )
      ).toBe('custom_fields.name:"status" AND custom_fields.value:paid')
    })

    it('uses the dotted names for notes', () => {
      expect(
        serializeAdvancedSearchQuery(
          group(
            And,
            atom(
              AdvancedSearchField.NoteText,
              AdvancedSearchOperator.AllWords,
              'call'
            ),
            atom(
              AdvancedSearchField.NoteAuthor,
              AdvancedSearchOperator.AllWords,
              'alice'
            )
          )
        )
      ).toBe('notes.note:call AND notes.user:alice')
    })

    it.each([
      [AdvancedSearchOperator.AllWords, ''],
      [AdvancedSearchOperator.AllWords, '  '],
      [AdvancedSearchOperator.AllWords, '!! --'],
      [AdvancedSearchOperator.Phrase, '""'],
      [AdvancedSearchOperator.StartsWith, 'two words'],
      [AdvancedSearchOperator.StartsWith, '***'],
      [AdvancedSearchOperator.StartsWith, undefined],
    ])('leaves out %s %j', (operator, value) => {
      expect(
        serializeAdvancedSearchQuery(
          atom(AdvancedSearchField.Title, operator, value)
        )
      ).toBe('')
    })
  })

  describe('checksum', () => {
    it('lowercases the prefix', () => {
      expect(
        serializeAdvancedSearchQuery(
          atom(
            AdvancedSearchField.Checksum,
            AdvancedSearchOperator.StartsWith,
            '9F86D081'
          )
        )
      ).toBe('checksum:9f86d081*')
    })
  })

  describe('number fields', () => {
    it.each([
      [AdvancedSearchOperator.Equals, '42', undefined, 'asn:42'],
      [AdvancedSearchOperator.AtLeast, '50', undefined, 'asn:[50 to]'],
      [AdvancedSearchOperator.AtMost, '50', undefined, 'asn:[to 50]'],
      [AdvancedSearchOperator.Between, '50', '150', 'asn:[50 to 150]'],
      [AdvancedSearchOperator.Equals, '4.2', undefined, ''],
      [AdvancedSearchOperator.Equals, '-1', undefined, ''],
      [AdvancedSearchOperator.Equals, '2024-01-01', undefined, ''],
      [AdvancedSearchOperator.Between, '50', '', ''],
    ])('%s %j %j writes %j', (operator, value, valueTo, expected) => {
      expect(
        serializeAdvancedSearchQuery(
          atom(AdvancedSearchField.ASN, operator, value, { valueTo })
        )
      ).toBe(expected)
    })
  })

  describe('date fields', () => {
    it.each([
      ['today', 'added:today'],
      ['previous month', 'added:"previous month"'],
      ['last tuesday', ''],
      ['', ''],
    ])('keyword %j writes %j', (value, expected) => {
      expect(
        serializeAdvancedSearchQuery(
          atom(
            AdvancedSearchField.Added,
            AdvancedSearchOperator.DateKeyword,
            value
          )
        )
      ).toBe(expected)
    })

    it.each([
      ['1', AdvancedSearchDateUnit.Day, 'added:[-1 day to now]'],
      ['3', AdvancedSearchDateUnit.Month, 'added:[-3 months to now]'],
      ['2', AdvancedSearchDateUnit.Week, 'added:[-2 weeks to now]'],
      ['0', AdvancedSearchDateUnit.Year, ''],
      ['1.5', AdvancedSearchDateUnit.Year, ''],
      ['3', undefined, ''],
      ['3', 'fortnight' as AdvancedSearchDateUnit, ''],
    ])('within the last %j %j writes %j', (value, unit, expected) => {
      expect(
        serializeAdvancedSearchQuery(
          atom(
            AdvancedSearchField.Added,
            AdvancedSearchOperator.WithinLast,
            value,
            {
              unit,
            }
          )
        )
      ).toBe(expected)
    })

    it.each([
      [
        AdvancedSearchOperator.AtLeast,
        '2024-01-01',
        undefined,
        'created:[2024-01-01 to]',
      ],
      [
        AdvancedSearchOperator.AtMost,
        '2024-01-01',
        undefined,
        'created:[to 2024-01-01]',
      ],
      [
        AdvancedSearchOperator.Between,
        '2024-01-01',
        '2024-03-31',
        'created:[2024-01-01 to 2024-03-31]',
      ],
      [AdvancedSearchOperator.AtLeast, '2024', undefined, ''],
      [AdvancedSearchOperator.Between, '2024-01-01', 'now', ''],
    ])('%s %j %j writes %j', (operator, value, valueTo, expected) => {
      expect(
        serializeAdvancedSearchQuery(
          atom(AdvancedSearchField.Created, operator, value, { valueTo })
        )
      ).toBe(expected)
    })
  })

  describe('groups', () => {
    const invoice = atom(
      AdvancedSearchField.Content,
      AdvancedSearchOperator.AllWords,
      'invoice'
    )
    const letter = atom(
      AdvancedSearchField.Title,
      AdvancedSearchOperator.AllWords,
      'letter'
    )
    const paid = atom(
      AdvancedSearchField.Tag,
      AdvancedSearchOperator.AllWords,
      'paid'
    )
    const twoWords = atom(
      AdvancedSearchField.Title,
      AdvancedSearchOperator.AllWords,
      'a b'
    )
    const anyWords = atom(
      AdvancedSearchField.Title,
      AdvancedSearchOperator.AnyWord,
      'a b'
    )
    const empty = atom(
      AdvancedSearchField.Title,
      AdvancedSearchOperator.AllWords,
      ''
    )

    it.each([
      ['an empty group', group(And), ''],
      ['a group of empty atoms', group(Or, empty, group(And, empty)), ''],
      [
        'a single child without parentheses',
        group(Or, invoice),
        'content:invoice',
      ],
      ['All', group(And, invoice, letter), 'content:invoice AND title:letter'],
      ['Any', group(Or, invoice, letter), 'content:invoice OR title:letter'],
      [
        'skipped empty atoms',
        group(And, empty, invoice, empty),
        'content:invoice',
      ],
      ['Not with one child', group(Not, paid), 'NOT tag:paid'],
      [
        'Not as none of',
        group(Not, paid, letter),
        'NOT (tag:paid OR title:letter)',
      ],
      [
        'Not with a compound child',
        group(Not, twoWords),
        'NOT (title:a AND title:b)',
      ],
      [
        'Not inside All',
        group(And, invoice, group(Not, paid)),
        'content:invoice AND NOT tag:paid',
      ],
      [
        'Not inside Any',
        group(Or, invoice, group(Not, paid)),
        'content:invoice OR NOT tag:paid',
      ],
      [
        'Any inside All',
        group(And, invoice, group(Or, letter, paid)),
        'content:invoice AND (title:letter OR tag:paid)',
      ],
      [
        'All inside Any',
        group(Or, invoice, group(And, letter, paid)),
        'content:invoice OR (title:letter AND tag:paid)',
      ],
      [
        'All inside All flattened',
        group(And, invoice, group(And, letter, paid)),
        'content:invoice AND title:letter AND tag:paid',
      ],
      [
        'an all-words atom inside Any',
        group(Or, invoice, twoWords),
        'content:invoice OR (title:a AND title:b)',
      ],
      [
        'an any-word atom inside All',
        group(And, invoice, anyWords),
        'content:invoice AND (title:a OR title:b)',
      ],
      [
        'an all-words atom inside Not with siblings',
        group(Not, paid, twoWords),
        'NOT (tag:paid OR (title:a AND title:b))',
      ],
    ])('writes %s', (_, tree, expected) => {
      expect(serializeAdvancedSearchQuery(tree)).toBe(expected)
    })

    it('writes the mockup example', () => {
      expect(
        serializeAdvancedSearchQuery(
          group(
            And,
            invoice,
            group(
              Or,
              atom(
                AdvancedSearchField.Correspondent,
                AdvancedSearchOperator.Phrase,
                'acme corp'
              ),
              atom(
                AdvancedSearchField.Content,
                AdvancedSearchOperator.Phrase,
                'acme corporation'
              )
            ),
            atom(
              AdvancedSearchField.Added,
              AdvancedSearchOperator.WithinLast,
              '3',
              {
                unit: AdvancedSearchDateUnit.Month,
              }
            ),
            group(Not, paid)
          )
        )
      ).toBe(
        'content:invoice AND (correspondent:"acme corp" OR content:"acme corporation") AND added:[-3 months to now] AND NOT tag:paid'
      )
    })
  })
})
