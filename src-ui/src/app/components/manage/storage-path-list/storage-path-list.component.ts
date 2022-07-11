import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { FILTER_STORAGE_PATH } from 'src/app/data/filter-rule-type'
import { PaperlessStoragePath } from 'src/app/data/paperless-storage-path'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { ToastService } from 'src/app/services/toast.service'
import { StoragePathEditDialogComponent } from '../../common/edit-dialog/storage-path-edit-dialog/storage-path-edit-dialog.component'
import { ManagementListComponent } from '../management-list/management-list.component'

@Component({
  selector: 'app-storage-path-list',
  templateUrl: './../management-list/management-list.component.html',
  styleUrls: ['./../management-list/management-list.component.scss'],
})
export class StoragePathListComponent extends ManagementListComponent<PaperlessStoragePath> {
  constructor(
    directoryService: StoragePathService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService
  ) {
    super(
      directoryService,
      modalService,
      StoragePathEditDialogComponent,
      toastService,
      documentListViewService,
      FILTER_STORAGE_PATH,
      $localize`storage path`,
      $localize`storage paths`,
      [
        {
          key: 'path',
          name: $localize`Path`,
          valueFn: (c: PaperlessStoragePath) => {
            return c.path
          },
        },
      ]
    )
  }

  getDeleteMessage(object: PaperlessStoragePath) {
    return $localize`Do you really want to delete the storage path "${object.name}"?`
  }
}
