import { HttpClient } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { CustomField } from 'src/app/data/custom-field'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class CustomFieldsService extends AbstractPaperlessService<CustomField> {
  constructor() {
    const http = inject(HttpClient)

    super(http, 'custom_fields')
  }
}
