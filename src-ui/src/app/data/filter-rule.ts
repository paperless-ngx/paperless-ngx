import { FilterRuleType } from './filter-rule-type';

export function cloneFilterRules(filterRules: FilterRule[]): FilterRule[] {
  if (filterRules) {
    let newRules: FilterRule[] = []
    for (let rule of filterRules) {
      newRules.push({type: rule.type, value: rule.value})
    }
    return newRules      
  } else {
    return null
  }
}

export interface FilterRule {
  type: FilterRuleType
  value: any
}