import { Injectable } from '@angular/core'
import { CustomField } from 'src/app/data/custom-field'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class CustomFieldsService extends AbstractPaperlessService<CustomField> {
  constructor() {
    super()
    this.resourceName = 'custom_fields'
  }
}
