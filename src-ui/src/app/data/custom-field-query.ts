import { debounceTime, distinctUntilChanged, Subject } from 'rxjs'
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
  IStartsWith = 'istartswith',
  IEndsWith = 'iendswith',
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
  [CustomFieldQueryOperator.IStartsWith]: $localize`Starts with (case-insensitive)`,
  [CustomFieldQueryOperator.IEndsWith]: $localize`Ends with (case-insensitive)`,
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
}

export const CUSTOM_FIELD_QUERY_OPERATORS_BY_GROUP = {
  [CustomFieldQueryOperatorGroups.Basic]: [
    CustomFieldQueryOperator.Exact,
    CustomFieldQueryOperator.In,
    CustomFieldQueryOperator.IsNull,
    CustomFieldQueryOperator.Exists,
  ],
  [CustomFieldQueryOperatorGroups.String]: [
    CustomFieldQueryOperator.IContains,
    CustomFieldQueryOperator.IStartsWith,
    CustomFieldQueryOperator.IEndsWith,
  ],
  [CustomFieldQueryOperatorGroups.Arithmetic]: [
    CustomFieldQueryOperator.GreaterThan,
    CustomFieldQueryOperator.GreaterThanOrEqual,
    CustomFieldQueryOperator.LessThan,
    CustomFieldQueryOperator.LessThanOrEqual,
    CustomFieldQueryOperator.Range,
  ],
  [CustomFieldQueryOperatorGroups.Containment]: [
    CustomFieldQueryOperator.Contains,
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
    CustomFieldQueryOperatorGroups.Arithmetic,
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
  ],
  [CustomFieldDataType.DocumentLink]: [
    CustomFieldQueryOperatorGroups.Basic,
    CustomFieldQueryOperatorGroups.Containment,
  ],
  [CustomFieldDataType.Select]: [CustomFieldQueryOperatorGroups.Basic],
}

export const CUSTOM_FIELD_QUERY_VALUE_TYPES_BY_OPERATOR = {
  [CustomFieldQueryOperator.Exact]: 'string',
  [CustomFieldQueryOperator.IsNull]: 'boolean',
  [CustomFieldQueryOperator.Exists]: 'boolean',
  [CustomFieldQueryOperator.IContains]: 'string',
  // TODO: Implement these
  // [CustomFieldQueryOperator.In]: 'array',
  // [CustomFieldQueryOperator.Contains]: 'string',
  // [CustomFieldQueryOperator.IStartsWith]: 'string',
  // [CustomFieldQueryOperator.IEndsWith]: 'string',
  // [CustomFieldQueryOperator.GreaterThan]: 'number',
  // [CustomFieldQueryOperator.GreaterThanOrEqual]: 'number',
  // [CustomFieldQueryOperator.LessThan]: 'number',
  // [CustomFieldQueryOperator.LessThanOrEqual]: 'number',
  // [CustomFieldQueryOperator.Range]: 'array',
}

export enum CustomFieldQueryElementType {
  Atom = 'Atom',
  Expression = 'Expression',
}

export class CustomFieldQueryElement {
  public readonly type: CustomFieldQueryElementType
  public changed: Subject<CustomFieldQueryElement>
  protected valueModelChanged: Subject<string | CustomFieldQueryElement[]>

  constructor(type: CustomFieldQueryElementType) {
    this.type = type
    this.changed = new Subject<CustomFieldQueryElement>()
    this.valueModelChanged = new Subject<string | CustomFieldQueryElement[]>()
    this.connectValueModelChanged()
  }

  protected connectValueModelChanged() {
    // Allows overriding in subclasses
    this.valueModelChanged.subscribe(() => {
      this.changed.next(this)
    })
  }

  public serialize() {
    throw new Error('Implemented in subclass')
  }

  public get isValid(): boolean {
    throw new Error('Implemented in subclass')
  }

  protected _operator: string = null
  public set operator(value: string) {
    this._operator = value
    this.changed.next(this)
  }
  public get operator(): string {
    return this._operator
  }

  protected _value: string | CustomFieldQueryElement[] = null
  public set value(value: string | CustomFieldQueryElement[]) {
    this._value = value
    this.valueModelChanged.next(value)
  }
  public get value(): string | CustomFieldQueryElement[] {
    return this._value
  }
}

export class CustomFieldQueryAtom extends CustomFieldQueryElement {
  protected _field: string
  set field(value: string) {
    this._field = value
    if (this.isValid) this.changed.next(this)
  }
  get field(): string {
    return this._field
  }

  override set operator(operator: string) {
    if (
      typeof this.value !== CUSTOM_FIELD_QUERY_VALUE_TYPES_BY_OPERATOR[operator]
    ) {
      switch (CUSTOM_FIELD_QUERY_VALUE_TYPES_BY_OPERATOR[operator]) {
        case 'string':
          this.value = ''
          break
        case 'boolean':
          this.value = 'true'
          break
        // TODO: Implement these
        default:
          this.value = null
          break
      }
    }
    super.operator = operator
  }

  override get operator(): string {
    // why?
    return super.operator
  }

  constructor(queryArray: [string, string, string] = [null, null, null]) {
    super(CustomFieldQueryElementType.Atom)
    ;[this._field, this._operator, this._value] = queryArray
  }

  protected override connectValueModelChanged(): void {
    this.valueModelChanged
      .pipe(debounceTime(1000), distinctUntilChanged())
      .subscribe(() => {
        this.changed.next(this)
      })
  }

  public override serialize() {
    return [this._field, this._operator, this._value.toString()]
  }

  public override get isValid(): boolean {
    return !!(this._field && this._operator && this._value !== null)
  }
}

export class CustomFieldQueryExpression extends CustomFieldQueryElement {
  constructor(
    expressionArray: [CustomFieldQueryLogicalOperator, any[]] = [
      CustomFieldQueryLogicalOperator.And,
      null,
    ]
  ) {
    super(CustomFieldQueryElementType.Expression)
    ;[this._operator] = expressionArray
    let values = expressionArray[1]
    if (!values) {
      this._value = []
    } else if (values?.length > 0 && values[0] instanceof Array) {
      this._value = values.map((value) => {
        if (value.length === 3) {
          const atom = new CustomFieldQueryAtom(value)
          atom.changed.subscribe(() => {
            this.changed.next(this)
          })
          return atom
        } else {
          const expression = new CustomFieldQueryExpression(value)
          expression.changed.subscribe(() => {
            this.changed.next(this)
          })
          return expression
        }
      })
    } else {
      this._value = [new CustomFieldQueryExpression(values as any)]
    }
  }

  public override serialize() {
    let value
    if (this._value instanceof Array) {
      value = this._value.map((atom) => atom.serialize())
    } else {
      value = value.serialize()
    }
    return [this._operator, value]
  }

  public override get isValid(): boolean {
    return (
      this._operator &&
      this._value.length > 0 &&
      (this._value as any[]).every((v) => v.isValid)
    )
  }
}
