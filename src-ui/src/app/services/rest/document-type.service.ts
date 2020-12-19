import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { AbstractPaperlessService } from './abstract-paperless-service';

@Injectable({
  providedIn: 'root'
})
export class DocumentTypeService extends AbstractPaperlessService<PaperlessDocumentType> {

  constructor(http: HttpClient) {
    super(http, 'document_types')
  }
}
