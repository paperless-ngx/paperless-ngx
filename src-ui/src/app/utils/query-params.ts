import { ParamMap, Params } from '@angular/router'
import {
  CustomFieldQueryLogicalOperator,
  CustomFieldQueryOperator,
} from '../data/custom-field-query'
import { FilterRule } from '../data/filter-rule'
import {
  FILTER_CUSTOM_FIELDS_QUERY,
  FILTER_HAS_CUSTOM_FIELDS_ALL,
  FILTER_HAS_CUSTOM_FIELDS_ANY,
  FILTER_RULE_TYPES,
  FilterRuleType,
} from '../data/filter-rule-type'
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

export function transformLegacyFilterRules(
  filterRules: FilterRule[]
): FilterRule[] {
  const LEGACY_CUSTOM_FIELD_FILTER_RULE_TYPES = [
    FILTER_HAS_CUSTOM_FIELDS_ANY,
    FILTER_HAS_CUSTOM_FIELDS_ALL,
  ]
  if (
    filterRules.filter((rule) =>
      LEGACY_CUSTOM_FIELD_FILTER_RULE_TYPES.includes(rule.rule_type)
    ).length
  ) {
    const anyRules = filterRules.filter(
      (rule) => rule.rule_type === FILTER_HAS_CUSTOM_FIELDS_ANY
    )
    const allRules = filterRules.filter(
      (rule) => rule.rule_type === FILTER_HAS_CUSTOM_FIELDS_ALL
    )
    const customFieldQueryLogicalOperator = allRules.length
      ? CustomFieldQueryLogicalOperator.And
      : CustomFieldQueryLogicalOperator.Or
    const valueRules = allRules.length ? allRules : anyRules
    const customFieldQueryExpression = [
      customFieldQueryLogicalOperator,
      [
        ...valueRules.map((rule) => [
          parseInt(rule.value),
          CustomFieldQueryOperator.Exists,
          true,
        ]),
      ],
    ]
    filterRules.push({
      rule_type: FILTER_CUSTOM_FIELDS_QUERY,
      value: JSON.stringify(customFieldQueryExpression),
    })
  }
  // TODO: can we support FILTER_DOES_NOT_HAVE_CUSTOM_FIELDS or FILTER_HAS_ANY_CUSTOM_FIELDS?
  return filterRules.filter(
    (rule) => !LEGACY_CUSTOM_FIELD_FILTER_RULE_TYPES.includes(rule.rule_type)
  )
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
  filterRulesFromQueryParams = transformLegacyFilterRules(
    filterRulesFromQueryParams
  )
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
