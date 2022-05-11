import { Injectable } from '@angular/core'
import { ParamMap, Params, Router } from '@angular/router'
import { FilterRule } from '../data/filter-rule'
import { FilterRuleType, FILTER_RULE_TYPES } from '../data/filter-rule-type'
import { PaperlessSavedView } from '../data/paperless-saved-view'
import { DocumentListViewService } from './document-list-view.service'

const SORT_FIELD_PARAMETER = 'sort'
const SORT_REVERSE_PARAMETER = 'reverse'

@Injectable({
  providedIn: 'root',
})
export class QueryParamsService {
  constructor(private router: Router, private list: DocumentListViewService) {}

  private filterParams: Params = {}
  private sortParams: Params = {}

  updateFilterRules(
    filterRules: FilterRule[],
    updateQueryParams: boolean = true
  ) {
    this.filterParams = filterRulesToQueryParams(filterRules)
    if (updateQueryParams) this.updateQueryParams()
  }

  set sortField(field: string) {
    this.sortParams[SORT_FIELD_PARAMETER] = field
    this.updateQueryParams()
  }

  set sortReverse(reverse: boolean) {
    if (!reverse) this.sortParams[SORT_REVERSE_PARAMETER] = undefined
    else this.sortParams[SORT_REVERSE_PARAMETER] = reverse
    this.updateQueryParams()
  }

  get params(): Params {
    return {
      ...this.sortParams,
      ...this.filterParams,
    }
  }

  private updateQueryParams() {
    // if we were on a saved view we navigate 'away' to /documents
    let base = []
    if (this.router.routerState.snapshot.url.includes('/view/'))
      base = ['/documents']

    this.router.navigate(base, {
      queryParams: this.params,
    })
  }

  public parseQueryParams(queryParams: ParamMap) {
    let filterRules = filterRulesFromQueryParams(queryParams)
    if (
      filterRules.length ||
      queryParams.has(SORT_FIELD_PARAMETER) ||
      queryParams.has(SORT_REVERSE_PARAMETER)
    ) {
      this.list.filterRules = filterRules
      this.list.sortField = queryParams.get(SORT_FIELD_PARAMETER)
      this.list.sortReverse =
        queryParams.has(SORT_REVERSE_PARAMETER) ||
        (!queryParams.has(SORT_FIELD_PARAMETER) &&
          !queryParams.has(SORT_REVERSE_PARAMETER))
      this.list.reload()
    } else if (
      filterRules.length == 0 &&
      !queryParams.has(SORT_FIELD_PARAMETER)
    ) {
      // this is navigating to /documents so we need to update the params from the list
      this.updateFilterRules(this.list.filterRules, false)
      this.sortParams[SORT_FIELD_PARAMETER] = this.list.sortField
      this.sortParams[SORT_REVERSE_PARAMETER] = this.list.sortReverse
      this.router.navigate([], {
        queryParams: this.params,
        replaceUrl: true,
      })
    }
  }

  updateFromView(view: PaperlessSavedView) {
    if (!this.router.routerState.snapshot.url.includes('/view/')) {
      // navigation for /documents?view=
      this.router.navigate([], {
        queryParams: { view: view.id },
      })
    }
    // make sure params are up-to-date
    this.updateFilterRules(view.filter_rules, false)
    this.sortParams[SORT_FIELD_PARAMETER] = this.list.sortField
    this.sortParams[SORT_REVERSE_PARAMETER] = this.list.sortReverse
  }

  navigateWithFilterRules(filterRules: FilterRule[]) {
    this.updateFilterRules(filterRules)
    this.router.navigate(['/documents'], {
      queryParams: this.params,
    })
  }
}

export function filterRulesToQueryParams(filterRules: FilterRule[]): Object {
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

export function filterRulesFromQueryParams(queryParams: ParamMap) {
  const allFilterRuleQueryParams: string[] = FILTER_RULE_TYPES.map(
    (rt) => rt.filtervar
  )

  // transform query params to filter rules
  let filterRulesFromQueryParams: FilterRule[] = []
  allFilterRuleQueryParams
    .filter((frqp) => queryParams.has(frqp))
    .forEach((filterQueryParamName) => {
      const rule_type: FilterRuleType = FILTER_RULE_TYPES.find(
        (rt) => rt.filtervar == filterQueryParamName
      )
      const valueURIComponent: string = queryParams.get(filterQueryParamName)
      const filterQueryParamValues: string[] = rule_type.multi
        ? valueURIComponent.split(',')
        : [valueURIComponent]

      filterRulesFromQueryParams = filterRulesFromQueryParams.concat(
        // map all values to filter rules
        filterQueryParamValues.map((val) => {
          return {
            rule_type: rule_type.id,
            value: val,
          }
        })
      )
    })

  return filterRulesFromQueryParams
}
