import { Injectable } from '@angular/core'
import { DocumentType } from 'src/app/data/document-type'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class DocumentTypeService extends AbstractNameFilterService<DocumentType> {
  constructor() {
    super()
    this.resourceName = 'document_types'
  }
}
