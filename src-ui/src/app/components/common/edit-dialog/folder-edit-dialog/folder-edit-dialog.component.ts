import { Component, OnInit } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { EditDialogComponent, EditDialogMode } from '../edit-dialog.component'
import { Folder } from 'src/app/data/folder'
import { FolderService } from 'src/app/services/rest/folder.service'

@Component({
  selector: 'pngx-folder-edit-dialog',
  templateUrl: './folder-edit-dialog.component.html',
  styleUrls: ['./folder-edit-dialog.component.scss'],
})
export class FolderEditDialogComponent
  extends EditDialogComponent<Folder>
  implements OnInit {
  private form: any
  constructor(
    service: FolderService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  ngOnInit(): void {
    super.ngOnInit()
    if (this.object?.type === 'folder') {
      this.form.patchValue({ merge: true })
    }
    if (this.typeFieldDisabled) {
    }
  }

  getCreateTitle() {
    return $localize`Create new folder`
  }

  getEditTitle() {
    return $localize`Edit folder`
  }

  getForm(): FormGroup {
    this.form = new FormGroup({
      name: new FormControl(null),
      permissions_form: new FormControl(null),
      merge: new FormControl(false),
    })
    return this.form
  }

  get typeFieldDisabled(): boolean {
    return this.dialogMode === EditDialogMode.EDIT
  }

  get hint(): string {

    return this.form.get('merge').value
      ? $localize`Existing owner, user and group permissions will be merged with these settings.`
      : $localize`Any and all existing owner, user and group permissions will be replaced.`
  }
}
