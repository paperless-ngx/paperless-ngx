import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { CustomField } from 'src/app/data/custom-field'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class CustomFieldsService extends AbstractPaperlessService<CustomField> {
  constructor(http: HttpClient) {
    super(http, 'custom_fields')
  }
}
