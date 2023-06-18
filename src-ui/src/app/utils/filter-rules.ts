import { FilterRule } from '../data/filter-rule'
import {
  FILTER_FULLTEXT_MORELIKE,
  FILTER_FULLTEXT_QUERY,
} from '../data/filter-rule-type'

export function cloneFilterRules(filterRules: FilterRule[]): FilterRule[] {
  if (filterRules) {
    let newRules: FilterRule[] = []
    for (let rule of filterRules) {
      newRules.push({ rule_type: rule.rule_type, value: rule.value })
    }
    return newRules
  } else {
    return null
  }
}

export function isFullTextFilterRule(filterRules: FilterRule[]): boolean {
  return (
    filterRules.find(
      (r) =>
        r.rule_type == FILTER_FULLTEXT_QUERY ||
        r.rule_type == FILTER_FULLTEXT_MORELIKE
    ) != null
  )
}

export function filterRulesDiffer(
  filterRulesA: FilterRule[],
  filterRulesB: FilterRule[]
): boolean {
  let differ = false
  if (filterRulesA.length != filterRulesB.length) {
    differ = true
  } else {
    differ = filterRulesA.some((rule) => {
      return (
        filterRulesB.find(
          (fri) => fri.rule_type == rule.rule_type && fri.value == rule.value
        ) == undefined
      )
    })
  }
  return differ
}
