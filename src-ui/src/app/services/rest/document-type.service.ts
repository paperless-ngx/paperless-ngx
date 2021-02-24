import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { AbstractNameFilterService } from './abstract-name-filter-service';

@Injectable({
  providedIn: 'root'
})
export class DocumentTypeService extends AbstractNameFilterService<PaperlessDocumentType> {

  constructor(http: HttpClient) {
    super(http, 'document_types')
  }
}
