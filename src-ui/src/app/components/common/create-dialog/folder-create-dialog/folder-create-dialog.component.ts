import { Component, OnInit } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'
import { PaperlessStoragePath } from 'src/app/data/paperless-storage-path'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { UserService } from 'src/app/services/rest/user.service'
import { EditDialogComponent } from '../../edit-dialog/edit-dialog.component'
import { Subscription } from 'rxjs'

@Component({
  selector: 'app-folder-create-dialog',
  templateUrl: './folder-create-dialog.component.html',
  styleUrls: ['./folder-create-dialog.component.scss'],
})
export class FolderCreateDialogComponent
  extends EditDialogComponent<PaperlessStoragePath>
  implements OnInit
{
  nameSub: Subscription

  constructor(
    service: StoragePathService,
    activeModal: NgbActiveModal,
    userService: UserService
  ) {
    super(service, activeModal, userService)
  }

  ngOnInit(): void {
    const nameField = this.objectForm.get('name')
    const parentFolderPath = this.object?.path ?? ''
    this.nameSub = nameField.valueChanges.subscribe(() => {
      const fullPath = parentFolderPath + '/' + nameField.value
      this.objectForm.get('path').patchValue(fullPath)
      this.objectForm.get('slug').patchValue(fullPath)
    })
  }

  submit(): void {
    this.nameSub.unsubscribe()
    this.objectForm.get('name').patchValue(this.objectForm.get('path').value)
    this.save()
  }

  getForm(): FormGroup<any> {
    return new FormGroup({
      name: new FormControl(''),
      path: new FormControl(''),
      slug: new FormControl(''),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }
}
