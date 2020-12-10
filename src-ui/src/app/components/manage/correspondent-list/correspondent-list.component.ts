import { Component, OnInit } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { environment } from 'src/environments/environment';
import { GenericListComponent } from '../generic-list/generic-list.component';
import { CorrespondentEditDialogComponent } from './correspondent-edit-dialog/correspondent-edit-dialog.component';

@Component({
  selector: 'app-correspondent-list',
  templateUrl: './correspondent-list.component.html',
  styleUrls: ['./correspondent-list.component.scss']
})
export class CorrespondentListComponent extends GenericListComponent<PaperlessCorrespondent> implements OnInit {

  constructor(correspondentsService: CorrespondentService, modalService: NgbModal, private titleService: Title) { 
    super(correspondentsService,modalService,CorrespondentEditDialogComponent)
  }

  getObjectName(object: PaperlessCorrespondent) {
    return `correspondent '${object.name}'`
  }

  ngOnInit(): void {
    super.ngOnInit()
    this.titleService.setTitle(`Correspondents - ${environment.appTitle}`)
  }

}
