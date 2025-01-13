import { FilterRule } from '../data/filter-rule'
import {
  FILTER_FULLTEXT_QUERY,
  FILTER_HAS_TAGS_ALL,
} from '../data/filter-rule-type'
import {
  cloneFilterRules,
  filterRulesDiffer,
  isFullTextFilterRule,
} from './filter-rules'

const filterRules: FilterRule[] = [
  {
    rule_type: FILTER_HAS_TAGS_ALL,
    value: '9',
  },
]

describe('FilterRules Utils', () => {
  it('should clone filter rules', () => {
    let rules = cloneFilterRules(filterRules)
    expect(rules).toEqual(filterRules)

    rules = cloneFilterRules(null)
    expect(rules).toBeNull()
  })

  it('should determine if filter rule is a full text rule', () => {
    const rules = [
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'hello',
      },
    ]
    expect(isFullTextFilterRule(rules)).toBeTruthy()
    expect(isFullTextFilterRule(filterRules)).toBeFalsy()
  })

  it('should determine if filter rule sets differ', () => {
    const rules2 = [
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'hello',
      },
    ]
    expect(filterRulesDiffer(filterRules, [])).toBeTruthy()
    expect(filterRulesDiffer(filterRules, rules2)).toBeTruthy()
    expect(filterRulesDiffer(filterRules, filterRules)).toBeFalsy()
  })
})
