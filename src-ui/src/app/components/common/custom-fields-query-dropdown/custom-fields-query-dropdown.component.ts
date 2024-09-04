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
  CustomFieldQueryElement,
} from 'src/app/data/custom-field-query'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'

export class CustomFieldQueriesModel {
  public queries: CustomFieldQueryElement[] = []

  public readonly changed = new Subject<CustomFieldQueriesModel>()

  public clear(fireEvent = true) {
    this.queries = []
    if (fireEvent) {
      this.changed.next(this)
    }
  }

  public addQuery(query: CustomFieldQueryAtom) {
    if (this.queries.length === 0) {
      this.addExpression()
    }
    ;(this.queries[0].value as CustomFieldQueryElement[]).push(query)
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
      ;(
        (this.queries[0] as CustomFieldQueryExpression)
          .value as CustomFieldQueryElement[]
      ).push(expression)
    } else {
      this.queries.push(expression)
    }
    expression.changed.subscribe(() => {
      this.changed.next(this)
    })
  }

  private findElement(queryElement: CustomFieldQueryElement, elements: any[]) {
    for (let i = 0; i < elements.length; i++) {
      if (elements[i] === queryElement) {
        return elements.splice(i, 1)[0]
      } else if (elements[i].type === CustomFieldQueryElementType.Expression) {
        let found = this.findElement(queryElement, elements[i].value as any[])
        if (found !== undefined) {
          return found
        }
      }
    }
    return undefined
  }

  public removeElement(queryElement: CustomFieldQueryElement) {
    let foundComponent
    for (let i = 0; i < this.queries.length; i++) {
      let query = this.queries[i]
      if (query === queryElement) {
        foundComponent = this.queries.splice(i, 1)[0]
        break
      } else if (query.type === CustomFieldQueryElementType.Expression) {
        let found = this.findElement(queryElement, query.value as any[])
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

  private _selectionModel: CustomFieldQueriesModel =
    new CustomFieldQueriesModel()

  @Input()
  set selectionModel(model: CustomFieldQueriesModel) {
    if (this._selectionModel) {
      this._selectionModel.changed.complete()
    }
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
    this.reset()
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }

  public onOpenChange(open: boolean) {
    if (open && this.selectionModel.queries.length === 0) {
      this.selectionModel.addExpression()
    }
  }

  public get isActive(): boolean {
    return (
      (this.selectionModel.queries[0] as CustomFieldQueryExpression)?.value
        ?.length > 0
    )
  }

  private getFields() {
    this.customFieldsService
      .listAll()
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe((result) => {
        this.customFields = result.results
      })
  }

  public addAtom(expression: CustomFieldQueryExpression) {
    expression.addAtom()
  }

  public addExpression(expression: CustomFieldQueryExpression) {
    expression.addExpression()
  }

  public removeElement(element: CustomFieldQueryElement) {
    this.selectionModel.removeElement(element)
  }

  public reset() {
    this.selectionModel.clear(false)
    this.selectionModel.changed.next(this.selectionModel)
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
