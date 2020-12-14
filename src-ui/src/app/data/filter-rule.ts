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

export interface FilterRule {
  rule_type: number
  value: any
}