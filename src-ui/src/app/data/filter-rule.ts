import { FilterRuleType } from './filter-rule-type';


export function filterRulesToQueryParams(filterRules: FilterRule[]) {
  let params = {}
  for (let rule of filterRules) {
    params[rule.type.filtervar] = rule.value
  }
  return params
}

export function cloneFilterRules(filterRules: FilterRule[]): FilterRule[] {
  let newRules: FilterRule[] = []
  for (let rule of filterRules) {
    newRules.push({type: rule.type, value: rule.value})
  }
  return newRules
}

export interface FilterRule {
  type: FilterRuleType
  value: any
}