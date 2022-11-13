import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { PaperlessGroup } from 'src/app/data/paperless-group'
import { PaperlessUser } from 'src/app/data/paperless-user'
import { GroupService } from 'src/app/services/rest/group.service'
import { UserService } from 'src/app/services/rest/user.service'

@Component({
  selector: 'app-user-edit-dialog',
  templateUrl: './user-edit-dialog.component.html',
  styleUrls: ['./user-edit-dialog.component.scss'],
})
export class UserEditDialogComponent extends EditDialogComponent<PaperlessUser> {
  groups: PaperlessGroup[]

  constructor(
    service: UserService,
    activeModal: NgbActiveModal,
    groupsService: GroupService
  ) {
    super(service, activeModal)

    groupsService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.groups = result.results))
  }

  getCreateTitle() {
    return $localize`Create new user account`
  }

  getEditTitle() {
    return $localize`Edit user account`
  }

  getForm(): FormGroup {
    return new FormGroup({
      username: new FormControl(''),
      first_name: new FormControl(''),
      last_name: new FormControl(''),
      is_active: new FormControl(''),
      is_superuser: new FormControl(''),
      groups: new FormControl(''),
      permissions: new FormControl(''),
    })
  }
}
