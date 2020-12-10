import { Component, OnInit } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { environment } from 'src/environments/environment';
import { GenericListComponent } from '../generic-list/generic-list.component';
import { DocumentTypeEditDialogComponent } from './document-type-edit-dialog/document-type-edit-dialog.component';

@Component({
  selector: 'app-document-type-list',
  templateUrl: './document-type-list.component.html',
  styleUrls: ['./document-type-list.component.scss']
})
export class DocumentTypeListComponent extends GenericListComponent<PaperlessDocumentType> implements OnInit {

  constructor(service: DocumentTypeService, modalService: NgbModal, private titleService: Title) {
    super(service, modalService, DocumentTypeEditDialogComponent)
  }

  getObjectName(object: PaperlessDocumentType) {
    return `document type '${object.name}'`
  }

  ngOnInit(): void {
    super.ngOnInit()
    this.titleService.setTitle(`Document types - ${environment.appTitle}`)
  }
}
