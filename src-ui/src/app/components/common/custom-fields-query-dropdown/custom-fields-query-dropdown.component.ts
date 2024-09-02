import { Component, EventEmitter, Input, Output } from '@angular/core'
import { Subject, first, takeUntil } from 'rxjs'
import { CustomField } from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'

export enum CustomFieldQueryLogicalOperator {
  And = 'AND',
  Or = 'OR',
  Not = 'NOT',
}

export enum CustomFieldQueryElementType {
  Atom = 'Atom',
  Expression = 'Expression',
}

export class CustomFieldQueryElement {
  public readonly type: CustomFieldQueryElementType
  public changed: Subject<CustomFieldQueryElement>

  constructor(type: CustomFieldQueryElementType) {
    this.type = type
    this.changed = new Subject<CustomFieldQueryElement>()
  }

  public serialize() {
    throw new Error('Implemented in subclass')
  }

  public get isValid(): boolean {
    throw new Error('Implemented in subclass')
  }

  protected _operator: string = null
  set operator(value: string) {
    this._operator = value
    this.changed.next(this)
  }
  get operator(): string {
    return this._operator
  }

  protected _value:
    | string
    | CustomFieldQueryAtom[]
    | CustomFieldQueryExpression[] = null
  set value(
    value: string | CustomFieldQueryAtom[] | CustomFieldQueryExpression[]
  ) {
    this._value = value
    this.changed.next(this)
  }
  get value(): string | CustomFieldQueryAtom[] | CustomFieldQueryExpression[] {
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

  constructor(queryArray: [string, string, string] = [null, null, null]) {
    super(CustomFieldQueryElementType.Atom)
    ;[this._field, this._operator, this._value] = queryArray
  }

  public serialize() {
    return [this._field, this._operator, this._value]
  }

  public get isValid(): boolean {
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

  public serialize() {
    let value
    if (this._value instanceof Array) {
      value = this._value.map((atom) => atom.serialize())
    } else {
      value = value.serialize()
    }
    return [this._operator, value]
  }

  public get isValid(): boolean {
    return (
      this._operator &&
      this._value.length > 0 &&
      (this._value as any[]).every((v) => v.isValid)
    )
  }
}

export class CustomFieldQueriesModel {
  public queries: Array<CustomFieldQueryAtom | CustomFieldQueryExpression> = []

  public readonly changed = new Subject<CustomFieldQueriesModel>()

  public clear(fireEvent = true) {
    this.queries = []
    if (fireEvent) {
      this.changed.next(this)
    }
  }

  public addQuery(
    query: CustomFieldQueryAtom = new CustomFieldQueryAtom([
      null,
      'exists',
      'true',
    ])
  ) {
    if (this.queries.length > 0) {
      if (this.queries[0].type === CustomFieldQueryElementType.Expression) {
        ;(this.queries[0].value as Array<any>).push(query)
      } else {
        this.queries.push(query)
      }
    } else {
      this.queries.push(query)
    }
    query.changed.subscribe(() => {
      if (query.field && query.operator && query.value) {
        this.changed.next(this)
      }
    })
  }

  public addExpression(
    expression: CustomFieldQueryExpression = new CustomFieldQueryExpression()
  ) {
    if (this.queries.length > 0) {
      if (this.queries[0].type === CustomFieldQueryElementType.Atom) {
        expression.value = this.queries as CustomFieldQueryAtom[]
        this.queries = []
      }
    }
    this.queries.push(expression)
    expression.changed.subscribe(() => {
      this.changed.next(this)
    })
  }

  private findComponent(
    queryComponent: CustomFieldQueryAtom | CustomFieldQueryExpression,
    components: any[]
  ) {
    for (let i = 0; i < components.length; i++) {
      if (components[i] === queryComponent) {
        return components.splice(i, 1)[0]
      } else if (
        components[i].type === CustomFieldQueryElementType.Expression
      ) {
        let found = this.findComponent(
          queryComponent,
          components[i].value as any[]
        )
        if (found !== undefined) {
          return found
        }
      }
    }
    return undefined
  }

  public removeComponent(
    queryComponent: CustomFieldQueryAtom | CustomFieldQueryExpression
  ) {
    let foundComponent
    for (let i = 0; i < this.queries.length; i++) {
      let query = this.queries[i]
      if (query === queryComponent) {
        foundComponent = this.queries.splice(i, 1)[0]
        break
      } else if (query.type === CustomFieldQueryElementType.Expression) {
        let found = this.findComponent(queryComponent, query.value as any[])
        if (found !== undefined) {
          foundComponent = found
        }
      }
    }
    if (foundComponent === undefined) {
      return
    }
    foundComponent.changed.complete()
    this.changed.next(this)
  }
}

@Component({
  selector: 'pngx-custom-fields-query-dropdown',
  templateUrl: './custom-fields-query-dropdown.component.html',
  styleUrls: ['./custom-fields-query-dropdown.component.scss'],
})
export class CustomFieldsQueryDropdownComponent {
  public CustomFieldQueryComponentType = CustomFieldQueryElementType

  @Input()
  title: string

  @Input()
  filterPlaceholder: string = ''

  @Input()
  icon: string

  @Input()
  allowSelectNone: boolean = false

  @Input()
  editing = false

  @Input()
  applyOnClose = false

  get name(): string {
    return this.title ? this.title.replace(/\s/g, '_').toLowerCase() : null
  }

  @Input()
  disabled: boolean = false

  _selectionModel: CustomFieldQueriesModel = new CustomFieldQueriesModel()

  @Input()
  set selectionModel(model: CustomFieldQueriesModel) {
    model.changed.subscribe((updatedModel) => {
      this.selectionModelChange.next(updatedModel)
    })
    this._selectionModel = model
  }

  get selectionModel(): CustomFieldQueriesModel {
    return this._selectionModel
  }

  @Output()
  selectionModelChange = new EventEmitter<CustomFieldQueriesModel>()

  customFields: CustomField[] = []

  private unsubscribeNotifier: Subject<any> = new Subject()

  constructor(protected customFieldsService: CustomFieldsService) {
    this.getFields()
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }

  private getFields() {
    this.customFieldsService
      .listAll()
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe((result) => {
        this.customFields = result.results
      })
  }

  public addAtom() {
    this.selectionModel.addQuery()
  }

  public addExpression() {
    this.selectionModel.addExpression()
  }

  public removeComponent(
    component: CustomFieldQueryAtom | CustomFieldQueryExpression
  ) {
    this.selectionModel.removeComponent(component)
  }

  public reset() {
    this.selectionModel.clear()
  }

  getOperatorsForField(field: CustomField): string[] {
    return ['exact', 'in', 'icontains', 'isnull', 'exists']
    // TODO: implement this
  }
}
