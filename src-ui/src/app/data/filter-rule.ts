import {
  FILTER_FULLTEXT_MORELIKE,
  FILTER_FULLTEXT_QUERY,
} from './filter-rule-type'

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
  let modified = false
  if (filterRulesA.length != filterRulesB.length) {
    modified = true
  } else {
    modified = filterRulesA.some((rule) => {
      return (
        filterRulesB.find(
          (fri) => fri.rule_type == rule.rule_type && fri.value == rule.value
        ) == undefined
      )
    })

    if (!modified) {
      // only check other direction if we havent already determined is modified
      modified = filterRulesB.some((rule) => {
        filterRulesA.find(
          (fr) => fr.rule_type == rule.rule_type && fr.value == rule.value
        ) == undefined
      })
    }
  }
  return modified
}

export interface FilterRule {
  rule_type: number
  value: string
}
