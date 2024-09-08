import { debounceTime, distinctUntilChanged, Subject } from 'rxjs'
import { CustomFieldDataType } from './custom-field'
import { v4 as uuidv4 } from 'uuid'

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
  [CustomFieldQueryOperator.Exact]: 'string',
  [CustomFieldQueryOperator.IsNull]: 'boolean',
  [CustomFieldQueryOperator.Exists]: 'boolean',
  [CustomFieldQueryOperator.IContains]: 'string',
  [CustomFieldQueryOperator.GreaterThanOrEqual]: 'string|number',
  [CustomFieldQueryOperator.LessThanOrEqual]: 'string|number',
  [CustomFieldQueryOperator.GreaterThan]: 'number',
  [CustomFieldQueryOperator.LessThan]: 'number',
  [CustomFieldQueryOperator.Contains]: 'array',
  // [CustomFieldQueryOperator.In]: 'array', // TODO: Implement
}

export const CUSTOM_FIELD_QUERY_MAX_DEPTH = 4
export const CUSTOM_FIELD_QUERY_MAX_ATOMS = 5

export enum CustomFieldQueryElementType {
  Atom = 'Atom',
  Expression = 'Expression',
}

export class CustomFieldQueryElement {
  public readonly type: CustomFieldQueryElementType
  public changed: Subject<CustomFieldQueryElement>
  protected valueModelChanged: Subject<
    string | string[] | number[] | CustomFieldQueryElement[]
  >
  public depth: number = 0
  public id: string = uuidv4()

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

  protected _operator: string = null
  public set operator(value: string) {
    this._operator = value
    this.changed.next(this)
  }
  public get operator(): string {
    return this._operator
  }

  protected _value: string | string[] | number[] | CustomFieldQueryElement[] =
    null
  public set value(
    value: string | string[] | number[] | CustomFieldQueryElement[]
  ) {
    this._value = value
    this.valueModelChanged.next(value)
  }
  public get value(): string | string[] | number[] | CustomFieldQueryElement[] {
    return this._value
  }
}

export class CustomFieldQueryAtom extends CustomFieldQueryElement {
  protected _field: number
  set field(field: any) {
    this._field = parseInt(field, 10)
    this.changed.next(this)
  }
  get field(): number {
    return this._field
  }

  override set operator(operator: string) {
    const newTypes: string[] =
      CUSTOM_FIELD_QUERY_VALUE_TYPES_BY_OPERATOR[operator]?.split('|')
    if (!newTypes) {
      this.value = null
    }
    if (!newTypes.includes(typeof this.value)) {
      if (newTypes.length === 1) {
        switch (newTypes[0]) {
          case 'string':
            this.value = ''
            break
          case 'boolean':
            this.value = 'true'
            break
          case 'number':
            try {
              this.value = parseFloat(this.value as string).toString()
            } catch (e) {
              this.value = null
            }
            break
          case 'array':
            this.value = []
            break
          default:
            this.value = null
            break
        }
      } else {
        if (newTypes.includes('number')) {
          try {
            this.value = parseFloat(this.value as string).toString()
          } catch (e) {
            this.value = null
          }
        } else {
          this.value = null
        }
      }
    } else if (
      ['true', 'false'].includes(this.value as string) &&
      newTypes.includes('string')
    ) {
      this.value = ''
    }
    super.operator = operator
  }

  override get operator(): string {
    // why?
    return super.operator
  }

  constructor(queryArray: [number, string, string] = [null, null, null]) {
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
    return [this._field, this._operator, this._value]
  }
}

export class CustomFieldQueryExpression extends CustomFieldQueryElement {
  constructor(
    expressionArray: [CustomFieldQueryLogicalOperator, any[]] = [
      CustomFieldQueryLogicalOperator.Or,
      null,
    ]
  ) {
    super(CustomFieldQueryElementType.Expression)
    let values
    ;[this._operator, values] = expressionArray
    if (!values) {
      this._value = []
    } else if (values?.length > 0 && values[0] instanceof Array) {
      this._value = values.map((value) => {
        if (value.length === 3) {
          const atom = new CustomFieldQueryAtom(value)
          atom.depth = this.depth + 1
          atom.changed.subscribe(() => {
            this.changed.next(this)
          })
          return atom
        } else {
          const expression = new CustomFieldQueryExpression(value)
          expression.depth = this.depth + 1
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

  public addAtom(
    atom: CustomFieldQueryAtom = new CustomFieldQueryAtom([
      null,
      CustomFieldQueryOperator.Exists,
      'true',
    ])
  ) {
    atom.depth = this.depth + 1
    ;(this._value as CustomFieldQueryElement[]).push(atom)
    atom.changed.subscribe(() => {
      this.changed.next(this)
    })
  }

  public addExpression(
    expression: CustomFieldQueryExpression = new CustomFieldQueryExpression()
  ) {
    expression.depth = this.depth + 1
    ;(this._value as CustomFieldQueryElement[]).push(expression)
    expression.changed.subscribe(() => {
      this.changed.next(this)
    })
  }
}
