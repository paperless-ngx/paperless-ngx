import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import {
  IMAPSecurity,
  IMAPSecurityLabels,
  PaperlessMailAccount,
} from 'src/app/data/paperless-mail-account'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'

@Component({
  selector: 'app-mail-account-edit-dialog',
  templateUrl: './mail-account-edit-dialog.component.html',
  styleUrls: ['./mail-account-edit-dialog.component.scss'],
})
export class MailAccountEditDialogComponent extends EditDialogComponent<PaperlessMailAccount> {
  constructor(service: MailAccountService, activeModal: NgbActiveModal) {
    super(service, activeModal)
  }

  getCreateTitle() {
    return $localize`Create new mail account`
  }

  getEditTitle() {
    return $localize`Edit mail account`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(null),
      imap_server: new FormControl(null),
      imap_port: new FormControl(null),
      imap_security: new FormControl(IMAPSecurity.SSL),
      username: new FormControl(null),
      password: new FormControl(null),
      character_set: new FormControl('UTF-8'),
    })
  }

  get imapSecurityOptions() {
    return IMAPSecurityLabels
  }
}
