import {
  Component,
  EventEmitter,
  Input,
  OnDestroy,
  Output,
  QueryList,
  ViewChild,
  ViewChildren,
} from '@angular/core'
import { NgbDropdown } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectComponent } from '@ng-select/ng-select'
import { Subject, first, takeUntil } from 'rxjs'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import {
  CustomFieldQueryElementType,
  CustomFieldQueryOperator,
  CUSTOM_FIELD_QUERY_OPERATOR_GROUPS_BY_TYPE,
  CUSTOM_FIELD_QUERY_OPERATORS_BY_GROUP,
  CustomFieldQueryOperatorGroups,
  CUSTOM_FIELD_QUERY_OPERATOR_LABELS,
  CUSTOM_FIELD_QUERY_MAX_DEPTH,
  CUSTOM_FIELD_QUERY_MAX_ATOMS,
} from 'src/app/data/custom-field-query'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import {
  CustomFieldQueryElement,
  CustomFieldQueryExpression,
  CustomFieldQueryAtom,
} from 'src/app/utils/custom-field-query-element'
import { popperOptionsReenablePreventOverflow } from 'src/app/utils/popper-options'

export class CustomFieldQueriesModel {
  public queries: CustomFieldQueryElement[] = []

  public readonly changed = new Subject<CustomFieldQueriesModel>()

  public clear(fireEvent = true) {
    this.queries = []
    if (fireEvent) {
      this.changed.next(this)
    }
  }

  public isValid(): boolean {
    return (
      this.queries.length > 0 &&
      this.validateExpression(this.queries[0] as CustomFieldQueryExpression)
    )
  }

  public isEmpty(): boolean {
    return (
      this.queries.length === 0 ||
      (this.queries.length === 1 && this.queries[0].value.length === 0)
    )
  }

  private validateAtom(atom: CustomFieldQueryAtom) {
    let valid = !!(atom.field && atom.operator && atom.value !== null)
    if (
      [
        CustomFieldQueryOperator.In.valueOf(),
        CustomFieldQueryOperator.Contains.valueOf(),
      ].includes(atom.operator) &&
      atom.value
    ) {
      valid = valid && atom.value.length > 0
    }
    return valid
  }

  private validateExpression(expression: CustomFieldQueryExpression) {
    return (
      expression.operator &&
      expression.value.length > 0 &&
      (expression.value as CustomFieldQueryElement[]).every((e) =>
        e.type === CustomFieldQueryElementType.Atom
          ? this.validateAtom(e as CustomFieldQueryAtom)
          : this.validateExpression(e as CustomFieldQueryExpression)
      )
    )
  }

  public addAtom(atom: CustomFieldQueryAtom) {
    if (this.queries.length === 0) {
      this.addExpression()
    }
    ;(this.queries[0].value as CustomFieldQueryElement[]).push(atom)
    atom.changed.subscribe(() => {
      if (atom.field && atom.operator && atom.value) {
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

  private findElement(
    queryElement: CustomFieldQueryElement,
    elements: any[]
  ): CustomFieldQueryElement {
    let foundElement
    for (let i = 0; i < elements.length; i++) {
      if (elements[i] === queryElement) {
        foundElement = elements.splice(i, 1)[0]
      } else if (elements[i].type === CustomFieldQueryElementType.Expression) {
        foundElement = this.findElement(
          queryElement,
          elements[i].value as CustomFieldQueryElement[]
        )
      }
      if (foundElement) {
        break
      }
    }
    return foundElement
  }

  public removeElement(queryElement: CustomFieldQueryElement) {
    let foundComponent
    for (let i = 0; i < this.queries.length; i++) {
      let query = this.queries[i]
      if (query === queryElement) {
        foundComponent = this.queries.splice(i, 1)[0]
        break
      } else if (query.type === CustomFieldQueryElementType.Expression) {
        foundComponent = this.findElement(queryElement, query.value as any[])
      }
    }
    if (foundComponent) {
      foundComponent.changed.complete()
      if (this.isEmpty()) {
        this.clear()
      }
      this.changed.next(this)
    }
  }
}

@Component({
  selector: 'pngx-custom-fields-query-dropdown',
  templateUrl: './custom-fields-query-dropdown.component.html',
  styleUrls: ['./custom-fields-query-dropdown.component.scss'],
})
export class CustomFieldsQueryDropdownComponent implements OnDestroy {
  public CustomFieldQueryComponentType = CustomFieldQueryElementType
  public CustomFieldQueryOperator = CustomFieldQueryOperator
  public CustomFieldDataType = CustomFieldDataType
  public CUSTOM_FIELD_QUERY_MAX_DEPTH = CUSTOM_FIELD_QUERY_MAX_DEPTH
  public CUSTOM_FIELD_QUERY_MAX_ATOMS = CUSTOM_FIELD_QUERY_MAX_ATOMS
  public popperOptions = popperOptionsReenablePreventOverflow

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

  @ViewChild('dropdown') dropdown: NgbDropdown

  @ViewChildren(NgSelectComponent) fieldSelects!: QueryList<NgSelectComponent>

  private _selectionModel: CustomFieldQueriesModel

  @Input()
  set selectionModel(model: CustomFieldQueriesModel) {
    if (this._selectionModel) {
      this._selectionModel.changed.complete()
    }
    model.changed.subscribe(() => {
      this.onModelChange()
    })
    this._selectionModel = model
  }

  get selectionModel(): CustomFieldQueriesModel {
    return this._selectionModel
  }

  private onModelChange() {
    if (this.selectionModel.isEmpty() || this.selectionModel.isValid()) {
      this.selectionModelChange.next(this.selectionModel)
      this.selectionModel.isEmpty() && this.dropdown?.close()
    }
  }

  @Output()
  selectionModelChange = new EventEmitter<CustomFieldQueriesModel>()

  customFields: CustomField[] = []

  private unsubscribeNotifier: Subject<any> = new Subject()

  constructor(protected customFieldsService: CustomFieldsService) {
    this.selectionModel = new CustomFieldQueriesModel()
    this.getFields()
    this.reset()
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }

  public onOpenChange(open: boolean) {
    if (open) {
      if (this.selectionModel.queries.length === 0) {
        this.selectionModel.addAtom(
          new CustomFieldQueryAtom([
            null,
            CustomFieldQueryOperator.Exists,
            'true',
          ])
        )
      }
      if (
        this.selectionModel.queries.length === 1 &&
        (
          (this.selectionModel.queries[0] as CustomFieldQueryExpression)
            ?.value[0] as CustomFieldQueryAtom
        )?.field === null
      ) {
        setTimeout(() => {
          this.fieldSelects.first?.focus()
        }, 0)
      }
    }
  }

  public get isActive(): boolean {
    return this.selectionModel.isValid()
  }

  private getFields() {
    this.customFieldsService
      .listAll()
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe((result) => {
        this.customFields = result.results
      })
  }

  public getCustomFieldByID(id: number): CustomField {
    return this.customFields.find((field) => field.id === id)
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

  getSelectOptionsForField(fieldID: number): string[] {
    const field = this.customFields.find((field) => field.id === fieldID)
    if (field) {
      return field.extra_data['select_options']
    }
    return []
  }
}
