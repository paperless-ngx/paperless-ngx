import { Subject, debounceTime, distinctUntilChanged } from 'rxjs'
import { v4 as uuidv4 } from 'uuid'
import {
  CustomFieldQueryElementType,
  CUSTOM_FIELD_QUERY_VALUE_TYPES_BY_OPERATOR,
  CustomFieldQueryLogicalOperator,
  CustomFieldQueryOperator,
} from '../data/custom-field-query'

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
    } else {
      if (!newTypes.includes(typeof this.value)) {
        switch (newTypes[0]) {
          case 'string':
            this.value = ''
            break
          case 'boolean':
            this.value = 'true'
            break
          case 'array':
            this.value = []
            break
          case 'number':
            const num = parseFloat(this.value as string)
            this.value = isNaN(num) ? null : num.toString()
            break
        }
      } else if (
        ['true', 'false'].includes(this.value as string) &&
        newTypes.includes('string')
      ) {
        this.value = ''
      }
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
  protected _value: string[] | number[] | CustomFieldQueryElement[]

  constructor(
    expressionArray: [CustomFieldQueryLogicalOperator, any[]] = [
      CustomFieldQueryLogicalOperator.Or,
      null,
    ]
  ) {
    super(CustomFieldQueryElementType.Expression)
    let values
    ;[this._operator, values] = expressionArray
    if (!values || values.length === 0) {
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
      const expression = new CustomFieldQueryExpression(values as any)
      expression.depth = this.depth + 1
      expression.changed.subscribe(() => {
        this.changed.next(this)
      })
      this._value = [expression]
    }
  }

  public override serialize() {
    let value
    value = this._value.map((element) => element.serialize())
    // If the expression is negated it should have only one child which is an expression
    if (
      this._operator === CustomFieldQueryLogicalOperator.Not &&
      value.length === 1
    ) {
      value = value[0]
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

  public get negatable(): boolean {
    return (
      this.value.length === 1 &&
      (this.value[0] as CustomFieldQueryElement).type ===
        CustomFieldQueryElementType.Expression
    )
  }
}
