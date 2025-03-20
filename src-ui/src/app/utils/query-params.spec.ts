import { convertToParamMap } from '@angular/router'
import { CustomFieldQueryLogicalOperator } from '../data/custom-field-query'
import { FilterRule } from '../data/filter-rule'
import {
  FILTER_CORRESPONDENT,
  FILTER_CUSTOM_FIELDS_QUERY,
  FILTER_HAS_ANY_TAG,
  FILTER_HAS_CUSTOM_FIELDS_ALL,
  FILTER_HAS_CUSTOM_FIELDS_ANY,
  FILTER_HAS_TAGS_ALL,
} from '../data/filter-rule-type'
import {
  filterRulesFromQueryParams,
  paramsFromViewState,
  paramsToViewState,
  queryParamsFromFilterRules,
  transformLegacyFilterRules,
} from './query-params'

const tags__id__all = '9'
const filterRules: FilterRule[] = [
  {
    rule_type: FILTER_HAS_TAGS_ALL,
    value: tags__id__all,
  },
]

describe('QueryParams Utils', () => {
  it('should convert view state to params', () => {
    let params = paramsFromViewState({
      sortField: 'added',
      sortReverse: true,
      currentPage: 2,
      filterRules,
    })
    expect(params).toEqual({
      sort: 'added',
      reverse: 1,
      page: 2,
      tags__id__all,
    })

    params = paramsFromViewState({
      sortField: 'created',
      sortReverse: false,
      currentPage: NaN,
      filterRules: [],
    })
    expect(params).toEqual({
      sort: 'created',
      reverse: undefined,
      page: 1,
    })

    params = paramsFromViewState(
      {
        sortField: 'created',
        sortReverse: false,
        currentPage: 1,
        filterRules: [],
      },
      true
    )
    expect(params).toEqual({
      page: undefined,
    })
  })

  it('should convert params to view state', () => {
    const params = {
      sort: 'created',
      reverse: 1,
      page: 1,
    }
    const state = paramsToViewState(convertToParamMap(params))
    expect(state).toMatchObject({
      currentPage: 1,
      sortField: 'created',
      sortReverse: true,
      filterRules: [],
    })
  })

  it('should convert params to filter rules', () => {
    let params = queryParamsFromFilterRules(filterRules)
    expect(params).toEqual({
      tags__id__all,
    })

    params = queryParamsFromFilterRules([
      {
        rule_type: FILTER_CORRESPONDENT,
        value: null,
      },
    ])
    expect(params).toEqual({
      correspondent__isnull: 1,
    })

    params = queryParamsFromFilterRules([
      {
        rule_type: FILTER_HAS_ANY_TAG,
        value: 'true',
      },
    ])
    expect(params).toEqual({
      is_tagged: 1,
    })

    params = queryParamsFromFilterRules([
      {
        rule_type: FILTER_HAS_ANY_TAG,
        value: 'false',
      },
    ])
    expect(params).toEqual({
      is_tagged: 0,
    })

    params = queryParamsFromFilterRules([
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: tags__id__all,
      },
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: '14',
      },
    ])
    expect(params).toEqual({
      tags__id__all: tags__id__all + ',14',
    })

    params = queryParamsFromFilterRules(null)
    expect(params).toBeNull()
  })

  it('should convert filter rules to query params', () => {
    let rules = filterRulesFromQueryParams(
      convertToParamMap({
        tags__id__all,
      })
    )
    expect(rules).toEqual([
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: tags__id__all,
      },
    ])

    rules = filterRulesFromQueryParams(
      convertToParamMap({
        tags__id__all: tags__id__all + ',13',
      })
    )
    expect(rules).toEqual([
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: tags__id__all,
      },
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: '13',
      },
    ])

    rules = filterRulesFromQueryParams(
      convertToParamMap({
        correspondent__id: '12',
      })
    )
    expect(rules).toEqual([
      {
        rule_type: FILTER_CORRESPONDENT,
        value: '12',
      },
    ])

    rules = filterRulesFromQueryParams(
      convertToParamMap({
        is_tagged: 'true',
      })
    )
    expect(rules).toEqual([
      {
        rule_type: FILTER_HAS_ANY_TAG,
        value: 'true',
      },
    ])

    rules = filterRulesFromQueryParams(
      convertToParamMap({
        correspondent__isnull: '1',
      })
    )
    expect(rules).toEqual([
      {
        rule_type: FILTER_CORRESPONDENT,
        value: null,
      },
    ])
  })

  it('should transform legacy filter rules', () => {
    let filterRules: FilterRule[] = [
      {
        rule_type: FILTER_HAS_CUSTOM_FIELDS_ANY,
        value: '1',
      },
      {
        rule_type: FILTER_HAS_CUSTOM_FIELDS_ANY,
        value: '2',
      },
    ]

    let transformedFilterRules = transformLegacyFilterRules(filterRules)

    expect(transformedFilterRules).toEqual([
      {
        rule_type: FILTER_CUSTOM_FIELDS_QUERY,
        value: JSON.stringify([
          CustomFieldQueryLogicalOperator.Or,
          [
            [1, 'exists', true],
            [2, 'exists', true],
          ],
        ]),
      },
    ])

    filterRules = [
      {
        rule_type: FILTER_HAS_CUSTOM_FIELDS_ALL,
        value: '3',
      },
      {
        rule_type: FILTER_HAS_CUSTOM_FIELDS_ALL,
        value: '4',
      },
    ]

    transformedFilterRules = transformLegacyFilterRules(filterRules)

    expect(transformedFilterRules).toEqual([
      {
        rule_type: FILTER_CUSTOM_FIELDS_QUERY,
        value: JSON.stringify([
          CustomFieldQueryLogicalOperator.And,
          [
            [3, 'exists', true],
            [4, 'exists', true],
          ],
        ]),
      },
    ])
  })
})
