import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { AbstractEdocService } from './abstract-edoc-service'
import { Observable } from 'rxjs'
import { CustomFieldInstance } from 'src/app/data/custom-field-instance'
import { AbstractNameFilterService } from './abstract-name-filter-service'
import { CustomField } from 'src/app/data/custom-field'

@Injectable({
  providedIn: 'root',
})
export class CustomFieldsService extends AbstractNameFilterService<CustomField> {
  constructor(http: HttpClient) {
    super(http, 'custom_fields')
  }
}
