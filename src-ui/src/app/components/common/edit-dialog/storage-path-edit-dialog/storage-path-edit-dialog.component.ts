import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { PaperlessStoragePath } from 'src/app/data/paperless-storage-path'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { ToastService } from 'src/app/services/toast.service'

@Component({
  selector: 'app-storage-path-edit-dialog',
  templateUrl: './storage-path-edit-dialog.component.html',
  styleUrls: ['./storage-path-edit-dialog.component.scss'],
})
export class StoragePathEditDialogComponent extends EditDialogComponent<PaperlessStoragePath> {
  constructor(
    service: StoragePathService,
    activeModal: NgbActiveModal,
    toastService: ToastService
  ) {
    super(service, activeModal, toastService)
  }

  get pathHint() {
    return (
      $localize`e.g.` +
      ' <code>{created_year}-{title}</code> ' +
      $localize`or use slashes to add directories e.g.` +
      ' <code>{created_year}/{correspondent}/{title}</code>. ' +
      $localize`See <a target="_blank" href="https://paperless-ngx.readthedocs.io/en/latest/advanced_usage.html#file-name-handling">documentation</a> for full list.`
    )
  }

  getCreateTitle() {
    return $localize`Create new storage path`
  }

  getEditTitle() {
    return $localize`Edit storage path`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      path: new FormControl(''),
      matching_algorithm: new FormControl(1),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
    })
  }
}
