import { getLocaleCurrencyCode } from '@angular/common'
import { Component, Inject, Input, LOCALE_ID, OnInit } from '@angular/core'
import { takeUntil } from 'rxjs'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { DisplayField, Document } from 'src/app/data/document'
import { Results } from 'src/app/data/results'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-custom-field-display',
  templateUrl: './custom-field-display.component.html',
  styleUrl: './custom-field-display.component.scss',
})
export class CustomFieldDisplayComponent
  extends LoadingComponentWithPermissions
  implements OnInit
{
  CustomFieldDataType = CustomFieldDataType

  private _document: Document
  @Input()
  set document(document: Document) {
    this._document = document
    this.init()
  }

  get document(): Document {
    return this._document
  }

  private _fieldId: number
  @Input()
  set fieldId(id: number) {
    this._fieldId = id
    this.init()
  }

  get fieldId(): number {
    return this._fieldId
  }

  @Input()
  set fieldDisplayKey(key: string) {
    this.fieldId = parseInt(key.replace(DisplayField.CUSTOM_FIELD, ''), 10)
  }

  @Input()
  showNameIfEmpty: boolean = false

  value: any
  currency: string

  private customFields: CustomField[] = []

  public field: CustomField

  private docLinkDocuments: Document[] = []

  private defaultCurrencyCode: any

  constructor(
    private customFieldService: CustomFieldsService,
    private documentService: DocumentService,
    @Inject(LOCALE_ID) currentLocale: string
  ) {
    super()
    this.defaultCurrencyCode = getLocaleCurrencyCode(currentLocale)
    this.customFieldService.listAll().subscribe((r) => {
      this.customFields = r.results
      this.init()
    })
  }

  ngOnInit(): void {
    this.init()
  }

  private init() {
    if (this.value || !this._fieldId || !this._document || !this.customFields) {
      return
    }
    this.field = this.customFields.find((f) => f.id === this._fieldId)
    this.value = this._document.custom_fields.find(
      (f) => f.field === this._fieldId
    )?.value
    if (this.value && this.field.data_type === CustomFieldDataType.Monetary) {
      this.currency =
        this.value.match(/([A-Z]{3})/)?.[0] ??
        this.field.extra_data?.default_currency ??
        this.defaultCurrencyCode
      this.value = parseFloat(this.value.replace(this.currency, ''))
    } else if (
      this.value?.length &&
      this.field.data_type === CustomFieldDataType.DocumentLink
    ) {
      this.getDocuments()
    }
  }

  private getDocuments() {
    this.documentService
      .getFew(this.value, { fields: 'id,title' })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((result: Results<Document>) => {
        this.docLinkDocuments = this.value
          .map((id) => result.results.find((d) => d.id === id))
          .filter((d) => d)
      })
  }

  public getDocumentTitle(docId: number): string {
    return this.docLinkDocuments?.find((d) => d.id === docId)?.title
  }

  public getSelectValue(field: CustomField, id: string): string {
    return field.extra_data.select_options?.find((o) => o.id === id)?.label
  }
}
