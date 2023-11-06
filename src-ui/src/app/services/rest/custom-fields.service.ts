import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { Observable } from 'rxjs'
import { PaperlessCustomField } from 'src/app/data/paperless-custom-field'
import { PaperlessCustomFieldInstance } from 'src/app/data/paperless-custom-field-instance'

@Injectable({
  providedIn: 'root',
})
export class CustomFieldsService extends AbstractPaperlessService<PaperlessCustomField> {
  constructor(http: HttpClient) {
    super(http, 'custom_fields')
  }
}
