import { Component, EventEmitter, Input, Output } from '@angular/core'
import { Subject, first, takeUntil } from 'rxjs'
import { CustomField } from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'

export class CustomFieldQuery {
  public changed = new Subject<CustomFieldQuery>()

  private _field: string
  set field(value: string) {
    this._field = value
    this.changed.next(this)
  }
  get field(): string {
    return this._field
  }

  private _operator: string
  set operator(value: string) {
    this._operator = value
    this.changed.next(this)
  }
  get operator(): string {
    return this._operator
  }

  private _value: string
  set value(value: string) {
    this._value = value
    this.changed.next(this)
  }
  get value(): string {
    return this._value
  }

  constructor(
    field: string = null,
    operator: string = null,
    value: string = null
  ) {
    this.field = field
    this.operator = operator
    this.value = value
  }
}

export class CustomFieldQueriesModel {
  // matchingModel: MatchingModel
  queries: CustomFieldQuery[] = []

  changed = new Subject<CustomFieldQueriesModel>()

  public clear(fireEvent = true) {
    this.queries = []
    if (fireEvent) {
      this.changed.next(this)
    }
  }

  public addQuery(query: CustomFieldQuery = new CustomFieldQuery()) {
    this.queries.push(query)
    query.changed.subscribe(() => {
      if (query.field && query.operator && query.value) {
        this.changed.next(this)
      }
    })
  }

  public removeQuery(index: number) {
    const query = this.queries.splice(index, 1)[0]
    query.changed.complete()
    this.changed.next(this)
  }
}

@Component({
  selector: 'pngx-custom-fields-lookup-dropdown',
  templateUrl: './custom-fields-lookup-dropdown.component.html',
  styleUrls: ['./custom-fields-lookup-dropdown.component.scss'],
})
export class CustomFieldsLookupDropdownComponent {
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

  public addQuery() {
    this.selectionModel.addQuery()
  }

  public removeQuery(index: number) {
    this.selectionModel.removeQuery(index)
  }

  getOperatorsForField(field: CustomField): string[] {
    return ['exact', 'in', 'isnull', 'exists']
    // TODO: implement this
  }
}
