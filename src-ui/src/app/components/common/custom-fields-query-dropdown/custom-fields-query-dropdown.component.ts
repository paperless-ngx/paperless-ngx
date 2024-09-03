import { Component, EventEmitter, Input, Output } from '@angular/core'
import { Subject, first, takeUntil } from 'rxjs'
import { CustomField } from 'src/app/data/custom-field'
import {
  CustomFieldQueryAtom,
  CustomFieldQueryExpression,
  CustomFieldQueryElementType,
  CustomFieldQueryOperator,
  CUSTOM_FIELD_QUERY_OPERATOR_GROUPS_BY_TYPE,
  CUSTOM_FIELD_QUERY_OPERATORS_BY_GROUP,
  CustomFieldQueryOperatorGroups,
  CUSTOM_FIELD_QUERY_OPERATOR_LABELS,
} from 'src/app/data/custom-field-query'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'

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
      CustomFieldQueryOperator.Exists,
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
  public CustomFieldQueryOperator = CustomFieldQueryOperator

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

  getOperatorsForField(
    fieldID: number
  ): Array<{ value: string; label: string }> {
    const field = this.customFields.find((field) => field.id === fieldID)
    const groups: CustomFieldQueryOperatorGroups[] = field
      ? CUSTOM_FIELD_QUERY_OPERATOR_GROUPS_BY_TYPE[field.data_type]
      : [CustomFieldQueryOperatorGroups.Basic]
    const operators = groups.flatMap(
      (group) => CUSTOM_FIELD_QUERY_OPERATORS_BY_GROUP[group]
    )
    return operators.map((operator) => ({
      value: operator,
      label: CUSTOM_FIELD_QUERY_OPERATOR_LABELS[operator],
    }))
  }
}
