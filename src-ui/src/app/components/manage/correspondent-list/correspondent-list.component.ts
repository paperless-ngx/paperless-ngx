import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { FILTER_CORRESPONDENT } from 'src/app/data/filter-rule-type';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { GenericListComponent } from '../generic-list/generic-list.component';
import { CorrespondentEditDialogComponent } from './correspondent-edit-dialog/correspondent-edit-dialog.component';

@Component({
  selector: 'app-correspondent-list',
  templateUrl: './correspondent-list.component.html',
  styleUrls: ['./correspondent-list.component.scss']
})
export class CorrespondentListComponent extends GenericListComponent<PaperlessCorrespondent> {

  constructor(correspondentsService: CorrespondentService, modalService: NgbModal,
    private router: Router,
    private list: DocumentListViewService
  ) { 
    super(correspondentsService,modalService,CorrespondentEditDialogComponent)
  }

  getDeleteMessage(object: PaperlessCorrespondent) {
    return $localize`Do you really want to delete the correspondent "${object.name}"?`
  }

  filterDocuments(object: PaperlessCorrespondent) {
    this.list.documentListView.filter_rules = [
      {rule_type: FILTER_CORRESPONDENT, value: object.id.toString()}
    ]
    this.router.navigate(["documents"])
  }
}
