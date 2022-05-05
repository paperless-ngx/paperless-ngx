import { Injectable } from '@angular/core'
import {
  ActivatedRoute,
  convertToParamMap,
  ParamMap,
  Params,
  Router,
} from '@angular/router'
import { FilterRule } from '../data/filter-rule'
import { FILTER_RULE_TYPES } from '../data/filter-rule-type'

@Injectable({
  providedIn: 'root',
})
export class QueryParamsService {
  constructor(private router: Router, private route: ActivatedRoute) {}

  private filterParams: Params
  private _filterRules: FilterRule[]

  set filterRules(filterRules: FilterRule[]) {
    this._filterRules = filterRules
    this.filterParams = this.filterRulesToQueryParams(filterRules)
  }

  get filterRules(): FilterRule[] {
    return this._filterRules
  }

  set params(params: any) {
    this.filterParams = params
    this._filterRules = this.filterRulesFromQueryParams(
      params.keys ? params : convertToParamMap(params) // ParamMap
    )
  }

  get params(): Params {
    return {
      ...this.filterParams,
    }
  }

  private filterRulesToQueryParams(filterRules: FilterRule[]): Object {
    if (filterRules) {
      let params = {}
      for (let rule of filterRules) {
        let ruleType = FILTER_RULE_TYPES.find((t) => t.id == rule.rule_type)
        if (ruleType.multi) {
          params[ruleType.filtervar] = params[ruleType.filtervar]
            ? params[ruleType.filtervar] + ',' + rule.value
            : rule.value
        } else if (ruleType.isnull_filtervar && rule.value == null) {
          params[ruleType.isnull_filtervar] = true
        } else {
          params[ruleType.filtervar] = rule.value
        }
      }
      return params
    } else {
      return null
    }
  }

  private filterRulesFromQueryParams(queryParams: ParamMap) {
    const allFilterRuleQueryParams: string[] = FILTER_RULE_TYPES.map(
      (rt) => rt.filtervar
    )

    // transform query params to filter rules
    let filterRulesFromQueryParams: FilterRule[] = []
    allFilterRuleQueryParams
      .filter((frqp) => queryParams.has(frqp))
      .forEach((filterQueryParamName) => {
        const filterQueryParamValues: string[] = queryParams
          .get(filterQueryParamName)
          .split(',')

        filterRulesFromQueryParams = filterRulesFromQueryParams.concat(
          // map all values to filter rules
          filterQueryParamValues.map((val) => {
            return {
              rule_type: FILTER_RULE_TYPES.find(
                (rt) => rt.filtervar == filterQueryParamName
              ).id,
              value: val,
            }
          })
        )
      })

    return filterRulesFromQueryParams
  }

  loadFilterRules(filterRules: FilterRule[]) {
    this.filterRules = filterRules
    this.router.navigate(['/documents'], {
      relativeTo: this.route,
      queryParams: this.params,
    })
  }
}
