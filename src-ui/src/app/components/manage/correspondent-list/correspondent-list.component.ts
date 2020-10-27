import { Component } from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { GenericListComponent } from '../generic-list/generic-list.component';
import { CorrespondentEditDialogComponent } from './correspondent-edit-dialog/correspondent-edit-dialog.component';

@Component({
  selector: 'app-correspondent-list',
  templateUrl: './correspondent-list.component.html',
  styleUrls: ['./correspondent-list.component.css']
})
export class CorrespondentListComponent extends GenericListComponent<PaperlessCorrespondent> {

  constructor(correspondentsService: CorrespondentService,
    modalService: NgbModal) { 
      super(correspondentsService,modalService,CorrespondentEditDialogComponent)
    }

}
