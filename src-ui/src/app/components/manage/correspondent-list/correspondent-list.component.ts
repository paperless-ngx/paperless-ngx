import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { FILTER_CORRESPONDENT } from 'src/app/data/filter-rule-type'
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { ToastService } from 'src/app/services/toast.service'
import { CorrespondentEditDialogComponent } from '../../common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component'
import { ManagementListComponent } from '../management-list/management-list.component'

@Component({
  selector: 'app-correspondent-list',
  templateUrl: './../management-list/management-list.component.html',
  styleUrls: ['./../management-list/management-list.component.scss'],
  providers: [{ provide: CustomDatePipe }],
})
export class CorrespondentListComponent extends ManagementListComponent<PaperlessCorrespondent> {
  constructor(
    correspondentsService: CorrespondentService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    private datePipe: CustomDatePipe
  ) {
    super(
      correspondentsService,
      modalService,
      CorrespondentEditDialogComponent,
      toastService,
      documentListViewService,
      FILTER_CORRESPONDENT,
      $localize`correspondent`,
      $localize`correspondents`,
      [
        {
          key: 'last_correspondence',
          name: $localize`Last used`,
          valueFn: (c: PaperlessCorrespondent) => {
            return this.datePipe.transform(c.last_correspondence)
          },
        },
      ]
    )
  }

  getDeleteMessage(object: PaperlessCorrespondent) {
    return $localize`Do you really want to delete the correspondent "${object.name}"?`
  }
}
