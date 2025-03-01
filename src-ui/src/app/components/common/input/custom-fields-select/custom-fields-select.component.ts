import { Component, forwardRef } from '@angular/core'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { RouterModule } from '@angular/router'
import { NgSelectModule } from '@ng-select/ng-select'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { AbstractInputComponent } from '../abstract-input'
import { CheckComponent } from '../check/check.component'
import { DateComponent } from '../date/date.component'
import { DocumentLinkComponent } from '../document-link/document-link.component'
import { MonetaryComponent } from '../monetary/monetary.component'
import { NumberComponent } from '../number/number.component'
import { SelectComponent } from '../select/select.component'
import { TextComponent } from '../text/text.component'
import { UrlComponent } from '../url/url.component'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CustomFieldsSelectComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-custom-fields-select',
  templateUrl: './custom-fields-select.component.html',
  styleUrls: ['./custom-fields-select.component.scss'],
  imports: [
    TextComponent,
    DateComponent,
    NumberComponent,
    DocumentLinkComponent,
    UrlComponent,
    SelectComponent,
    MonetaryComponent,
    CheckComponent,
    NgSelectModule,
    FormsModule,
    ReactiveFormsModule,
    RouterModule,
    NgxBootstrapIconsModule,
  ],
})
export class CustomFieldsSelectComponent extends AbstractInputComponent<Object> {
  public CustomFieldDataType = CustomFieldDataType

  constructor(customFieldsService: CustomFieldsService) {
    super()
    customFieldsService.listAll().subscribe((items) => {
      this.fields = items.results
    })
  }

  fields: CustomField[]

  _selectedFields: number[]
  set selectedFields(newFields: number[]) {
    this._selectedFields = newFields
    // map the selected fields to an object with field_id as key and value as value
    this.value = newFields.reduce((acc, fieldId) => {
      acc[fieldId] = this.value?.[fieldId] || null
      return acc
    }, {})
    this.onChange(this.value)
  }
  get selectedFields(): number[] {
    return this._selectedFields
  }

  writeValue(newValue: Object): void {
    // value will be a json object with field_id as key and value as value
    this._selectedFields = newValue
      ? this.fields
          .filter((field) => field.id in newValue)
          .map((field) => field.id)
      : []
    super.writeValue(newValue)
  }

  public getCustomField(id: number): CustomField {
    return this.fields.find((field) => field.id === id)
  }

  public removeField(fieldId: number): void {
    this.selectedFields = this.selectedFields.filter((id) => id !== fieldId)
  }
}
