import { CustomFieldDataType } from './custom-field'

export enum CustomFieldQueryLogicalOperator {
  And = 'AND',
  Or = 'OR',
  Not = 'NOT',
}

export enum CustomFieldQueryOperator {
  Exact = 'exact',
  In = 'in',
  IsNull = 'isnull',
  Exists = 'exists',
  Contains = 'contains',
  IContains = 'icontains',
  GreaterThan = 'gt',
  GreaterThanOrEqual = 'gte',
  LessThan = 'lt',
  LessThanOrEqual = 'lte',
  Range = 'range',
}

export const CUSTOM_FIELD_QUERY_OPERATOR_LABELS = {
  [CustomFieldQueryOperator.Exact]: $localize`Equal to`,
  [CustomFieldQueryOperator.In]: $localize`In`,
  [CustomFieldQueryOperator.IsNull]: $localize`Is null`,
  [CustomFieldQueryOperator.Exists]: $localize`Exists`,
  [CustomFieldQueryOperator.Contains]: $localize`Contains`,
  [CustomFieldQueryOperator.IContains]: $localize`Contains (case-insensitive)`,
  [CustomFieldQueryOperator.GreaterThan]: $localize`Greater than`,
  [CustomFieldQueryOperator.GreaterThanOrEqual]: $localize`Greater than or equal to`,
  [CustomFieldQueryOperator.LessThan]: $localize`Less than`,
  [CustomFieldQueryOperator.LessThanOrEqual]: $localize`Less than or equal to`,
  [CustomFieldQueryOperator.Range]: $localize`Range`,
}

export enum CustomFieldQueryOperatorGroups {
  Basic = 'basic',
  String = 'string',
  Arithmetic = 'arithmetic',
  Containment = 'containment',
  Subset = 'subset',
  Date = 'date',
}

// Modified from filters.py > SUPPORTED_EXPR_OPERATORS
export const CUSTOM_FIELD_QUERY_OPERATORS_BY_GROUP = {
  [CustomFieldQueryOperatorGroups.Basic]: [
    CustomFieldQueryOperator.Exists,
    CustomFieldQueryOperator.IsNull,
    CustomFieldQueryOperator.Exact,
  ],
  [CustomFieldQueryOperatorGroups.String]: [CustomFieldQueryOperator.IContains],
  [CustomFieldQueryOperatorGroups.Arithmetic]: [
    CustomFieldQueryOperator.GreaterThan,
    CustomFieldQueryOperator.GreaterThanOrEqual,
    CustomFieldQueryOperator.LessThan,
    CustomFieldQueryOperator.LessThanOrEqual,
  ],
  [CustomFieldQueryOperatorGroups.Containment]: [
    CustomFieldQueryOperator.Contains,
  ],
  [CustomFieldQueryOperatorGroups.Subset]: [CustomFieldQueryOperator.In],
  [CustomFieldQueryOperatorGroups.Date]: [
    CustomFieldQueryOperator.GreaterThanOrEqual,
    CustomFieldQueryOperator.LessThanOrEqual,
  ],
}

// filters.py > SUPPORTED_EXPR_CATEGORIES
export const CUSTOM_FIELD_QUERY_OPERATOR_GROUPS_BY_TYPE = {
  [CustomFieldDataType.String]: [
    CustomFieldQueryOperatorGroups.Basic,
    CustomFieldQueryOperatorGroups.String,
  ],
  [CustomFieldDataType.Url]: [
    CustomFieldQueryOperatorGroups.Basic,
    CustomFieldQueryOperatorGroups.String,
  ],
  [CustomFieldDataType.Date]: [
    CustomFieldQueryOperatorGroups.Basic,
    CustomFieldQueryOperatorGroups.Date,
  ],
  [CustomFieldDataType.Boolean]: [CustomFieldQueryOperatorGroups.Basic],
  [CustomFieldDataType.Integer]: [
    CustomFieldQueryOperatorGroups.Basic,
    CustomFieldQueryOperatorGroups.Arithmetic,
  ],
  [CustomFieldDataType.Float]: [
    CustomFieldQueryOperatorGroups.Basic,
    CustomFieldQueryOperatorGroups.Arithmetic,
  ],
  [CustomFieldDataType.Monetary]: [
    CustomFieldQueryOperatorGroups.Basic,
    CustomFieldQueryOperatorGroups.String,
    CustomFieldQueryOperatorGroups.Arithmetic,
  ],
  [CustomFieldDataType.DocumentLink]: [
    CustomFieldQueryOperatorGroups.Basic,
    CustomFieldQueryOperatorGroups.Containment,
  ],
  [CustomFieldDataType.Select]: [
    CustomFieldQueryOperatorGroups.Basic,
    CustomFieldQueryOperatorGroups.Subset,
  ],
}

export const CUSTOM_FIELD_QUERY_VALUE_TYPES_BY_OPERATOR = {
  [CustomFieldQueryOperator.Exact]: 'string|boolean',
  [CustomFieldQueryOperator.IsNull]: 'boolean',
  [CustomFieldQueryOperator.Exists]: 'boolean',
  [CustomFieldQueryOperator.IContains]: 'string',
  [CustomFieldQueryOperator.GreaterThanOrEqual]: 'string|number',
  [CustomFieldQueryOperator.LessThanOrEqual]: 'string|number',
  [CustomFieldQueryOperator.GreaterThan]: 'number',
  [CustomFieldQueryOperator.LessThan]: 'number',
  [CustomFieldQueryOperator.Contains]: 'array',
  [CustomFieldQueryOperator.In]: 'array',
}

export const CUSTOM_FIELD_QUERY_MAX_DEPTH = 4
export const CUSTOM_FIELD_QUERY_MAX_ATOMS = 5

export enum CustomFieldQueryElementType {
  Atom = 'Atom',
  Expression = 'Expression',
}
