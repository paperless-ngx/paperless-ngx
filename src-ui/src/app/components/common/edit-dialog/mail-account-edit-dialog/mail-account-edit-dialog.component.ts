import { Component, ViewChild } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal, NgbAlert } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { IMAPSecurity, MailAccount } from 'src/app/data/mail-account'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'

const IMAP_SECURITY_OPTIONS = [
  { id: IMAPSecurity.None, name: $localize`No encryption` },
  { id: IMAPSecurity.SSL, name: $localize`SSL` },
  { id: IMAPSecurity.STARTTLS, name: $localize`STARTTLS` },
]

@Component({
  selector: 'pngx-mail-account-edit-dialog',
  templateUrl: './mail-account-edit-dialog.component.html',
  styleUrls: ['./mail-account-edit-dialog.component.scss'],
})
export class MailAccountEditDialogComponent extends EditDialogComponent<MailAccount> {
  testActive: boolean = false
  testResult: string
  alertTimeout

  @ViewChild('testResultAlert', { static: false }) testResultAlert: NgbAlert

  constructor(
    service: MailAccountService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
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
      is_token: new FormControl(false),
      character_set: new FormControl('UTF-8'),
    })
  }

  get imapSecurityOptions() {
    return IMAP_SECURITY_OPTIONS
  }

  test() {
    this.testActive = true
    this.testResult = null
    clearTimeout(this.alertTimeout)
    const mailService = this.service as MailAccountService
    const newObject = Object.assign(
      Object.assign({}, this.object),
      this.objectForm.value
    )
    mailService.test(newObject).subscribe({
      next: (result: { success: boolean }) => {
        this.testActive = false
        this.testResult = result.success ? 'success' : 'danger'
        this.alertTimeout = setTimeout(() => this.testResultAlert.close(), 5000)
      },
      error: (e) => {
        this.testActive = false
        this.testResult = 'danger'
        this.alertTimeout = setTimeout(() => this.testResultAlert.close(), 5000)
      },
    })
  }

  get testResultMessage() {
    return this.testResult === 'success'
      ? $localize`Successfully connected to the mail server`
      : $localize`Unable to connect to the mail server`
  }
}
