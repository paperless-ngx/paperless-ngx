import { AfterViewInit, Component, OnInit } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { Subscription } from 'rxjs'
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'
import { PaperlessStoragePath } from 'src/app/data/paperless-storage-path'
import { PermissionsService } from 'src/app/services/permissions.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { UserService } from 'src/app/services/rest/user.service'
import { EditDialogComponent } from '../../edit-dialog/edit-dialog.component'
import { SettingsService } from 'src/app/services/settings.service'

@Component({
  selector: 'app-folder-create-dialog',
  templateUrl: './folder-create-dialog.component.html',
  styleUrls: ['./folder-create-dialog.component.scss'],
})
export class FolderCreateDialogComponent
  extends EditDialogComponent<PaperlessStoragePath>
  implements OnInit, AfterViewInit {
  nameSub: Subscription

  constructor(
    service: StoragePathService,
    activeModal: NgbActiveModal,
    userService: UserService,
    private settingsService: SettingsService
  ) {
    super(service, activeModal, userService)
  }

  ngOnInit(): void {
    const nameField = this.objectForm.get('name')
    const parentFolderPath = this.object?.path ?? ''
    this.nameSub = nameField.valueChanges.subscribe(() => {
      let fullPath = parentFolderPath + '/' + nameField.value
      if (fullPath.charAt(0) === '/') fullPath = fullPath.slice(1)
      this.objectForm.get('path').patchValue(fullPath)
      this.objectForm.get('slug').patchValue(fullPath)
    })
  }

  ngAfterViewInit(): void {
    this.objectForm.get('permissions_form').patchValue({
      owner: this.settingsService.currentUser.id,
      set_permissions: {
        view: { users: [], groups: [] },
        change: { users: [], groups: this.settingsService.currentUser.groups },
      },
    })
  }

  submit(): void {
    this.nameSub.unsubscribe()
    // This has to be done here, if we do it in the subscription,
    // user's input will get constantly interrupted
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
