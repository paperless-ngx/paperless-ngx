import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { PaperlessGroup } from 'src/app/data/paperless-group'
import { GroupService } from 'src/app/services/rest/group.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { PaperlessSSOGroup } from '../../../../data/paperless-sso-group'
import { SsoGroupService } from '../../../../services/rest/sso-group.service'
import { first } from 'rxjs'

@Component({
  selector: 'app-sso-group-edit-dialog',
  templateUrl: './sso-group-edit-dialog.component.html',
  styleUrls: ['./sso-group-edit-dialog.component.scss'],
})
export class SsoGroupEditDialogComponent extends EditDialogComponent<PaperlessSSOGroup> {
  groups: PaperlessGroup[]

  constructor(
    service: SsoGroupService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService,
    groupsService: GroupService
  ) {
    super(service, activeModal, userService, settingsService)

    groupsService
      .listAll()
      .pipe(first())
      .subscribe((result) => {
        this.groups = result.results
      })
  }

  getCreateTitle() {
    return $localize`Create new sso group`
  }

  getEditTitle() {
    return $localize`Edit sso group`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      group: new FormControl(null),
    })
  }
}
