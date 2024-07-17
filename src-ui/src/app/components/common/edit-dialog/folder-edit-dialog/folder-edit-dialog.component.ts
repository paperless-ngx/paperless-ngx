import { Component, OnInit } from '@angular/core'
import { FormGroup, FormControl } from '@angular/forms'
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
    return new FormGroup({
      name: new FormControl(null),
      permissions_form: new FormControl(null),
    })
  }

  get typeFieldDisabled(): boolean {
    return this.dialogMode === EditDialogMode.EDIT
  }
}
