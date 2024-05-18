import { ParamMap, Params } from '@angular/router'
import { FilterRule } from '../data/filter-rule'
import { FilterRuleType, FILTER_RULE_TYPES } from '../data/filter-rule-type'
import { ListViewState } from '../services/document-list-view.service'

const SORT_FIELD_PARAMETER = 'sort'
const SORT_REVERSE_PARAMETER = 'reverse'
const PAGE_PARAMETER = 'page'

export function paramsFromViewState(
  viewState: ListViewState,
  pageOnly: boolean = false
): Params {
  let params = queryParamsFromFilterRules(viewState.filterRules)
  params[SORT_FIELD_PARAMETER] = viewState.sortField
  params[SORT_REVERSE_PARAMETER] = viewState.sortReverse ? 1 : undefined
  if (pageOnly) params = {}
  params[PAGE_PARAMETER] = isNaN(viewState.currentPage)
    ? 1
    : viewState.currentPage
  if (pageOnly && viewState.currentPage == 1) params[PAGE_PARAMETER] = undefined
  return params
}

export function paramsToViewState(queryParams: ParamMap): ListViewState {
  let filterRules = filterRulesFromQueryParams(queryParams)
  let sortField = queryParams.get(SORT_FIELD_PARAMETER)
  let sortReverse =
    queryParams.has(SORT_REVERSE_PARAMETER) ||
    (!queryParams.has(SORT_FIELD_PARAMETER) &&
      !queryParams.has(SORT_REVERSE_PARAMETER))
  let currentPage = queryParams.has(PAGE_PARAMETER)
    ? parseInt(queryParams.get(PAGE_PARAMETER))
    : 1
  return {
    currentPage: currentPage,
    filterRules: filterRules,
    sortField: sortField,
    sortReverse: sortReverse,
  }
}

export function filterRulesFromQueryParams(
  queryParams: ParamMap
): FilterRule[] {
  const allFilterRuleQueryParams: string[] = FILTER_RULE_TYPES.map(
    (rt) => rt.filtervar
  )
    .concat(FILTER_RULE_TYPES.map((rt) => rt.isnull_filtervar))
    .filter((rt) => rt !== undefined)

  // transform query params to filter rules
  let filterRulesFromQueryParams: FilterRule[] = []
  allFilterRuleQueryParams
    .filter((frqp) => queryParams.has(frqp))
    .forEach((filterQueryParamName) => {
      const rule_type: FilterRuleType = FILTER_RULE_TYPES.find(
        (rt) =>
          rt.filtervar == filterQueryParamName ||
          rt.isnull_filtervar == filterQueryParamName
      )
      const isNullRuleType = rule_type.isnull_filtervar == filterQueryParamName
      const valueURIComponent: string = queryParams.get(filterQueryParamName)
      const filterQueryParamValues: string[] = rule_type.multi
        ? valueURIComponent.split(',')
        : [valueURIComponent]

      filterRulesFromQueryParams = filterRulesFromQueryParams.concat(
        // map all values to filter rules
        filterQueryParamValues.map((val) => {
          if (rule_type.datatype == 'boolean')
            val = val.replace('1', 'true').replace('0', 'false')
          return {
            rule_type: rule_type.id,
            value: isNullRuleType ? null : val,
          }
        })
      )
    })

  return filterRulesFromQueryParams
}

export function queryParamsFromFilterRules(filterRules: FilterRule[]): Params {
  if (filterRules) {
    let params = {}
    for (let rule of filterRules) {
      let ruleType = FILTER_RULE_TYPES.find((t) => t.id == rule.rule_type)
      if (ruleType.isnull_filtervar && rule.value == null) {
        params[ruleType.isnull_filtervar] = 1
      } else if (ruleType.multi) {
        params[ruleType.filtervar] = params[ruleType.filtervar]
          ? params[ruleType.filtervar] + ',' + rule.value
          : rule.value
      } else {
        params[ruleType.filtervar] = rule.value
        if (ruleType.datatype == 'boolean')
          params[ruleType.filtervar] =
            rule.value == 'true' || rule.value == '1' ? 1 : 0
      }
    }
    return params
  } else {
    return null
  }
}
