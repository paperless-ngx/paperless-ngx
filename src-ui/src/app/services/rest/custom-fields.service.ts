import { Injectable } from '@angular/core'
import { HttpClient } from '@angular/common/http'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { CustomField } from 'src/app/data/custom-field'

@Injectable({
  providedIn: 'root',
})
export class CustomFieldsService extends AbstractPaperlessService<CustomField> {
  constructor(http: HttpClient) {
    super(http, 'custom_fields')
  }
}
