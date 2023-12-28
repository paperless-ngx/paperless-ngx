import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { Observable } from 'rxjs'
import { CustomField } from 'src/app/data/custom-field'
import { CustomFieldInstance } from 'src/app/data/custom-field-instance'

@Injectable({
  providedIn: 'root',
})
export class CustomFieldsService extends AbstractPaperlessService<CustomField> {
  constructor(http: HttpClient) {
    super(http, 'custom_fields')
  }
}
