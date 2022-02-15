import { FILTER_FULLTEXT_MORELIKE, FILTER_FULLTEXT_QUERY } from "./filter-rule-type"

export function cloneFilterRules(filterRules: FilterRule[]): FilterRule[] {
  if (filterRules) {
    let newRules: FilterRule[] = []
    for (let rule of filterRules) {
      newRules.push({rule_type: rule.rule_type, value: rule.value})
    }
    return newRules
  } else {
    return null
  }
}

export function isFullTextFilterRule(filterRules: FilterRule[]): boolean {
  return filterRules.find(r => r.rule_type == FILTER_FULLTEXT_QUERY || r.rule_type == FILTER_FULLTEXT_MORELIKE) != null
}

export interface FilterRule {
  rule_type: number
  value: string
}
