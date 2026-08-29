import { Component, inject, OnInit, signal, ViewChild } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbAlert, NgbAlertModule } from '@ng-bootstrap/ng-bootstrap'
import { pairwise, startWith, takeUntil } from 'rxjs'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import {
  IMAP_DEFAULT_PORTS,
  IMAPSecurity,
  MailAccount,
} from 'src/app/data/mail-account'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CheckComponent } from '../../input/check/check.component'
import { PasswordComponent } from '../../input/password/password.component'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'

const IMAP_SECURITY_OPTIONS = [
  { id: IMAPSecurity.None, name: $localize`No encryption` },
  { id: IMAPSecurity.SSL, name: $localize`SSL` },
  { id: IMAPSecurity.STARTTLS, name: $localize`STARTTLS` },
]

const DEFAULT_IMAP_SECURITY = IMAPSecurity.SSL

@Component({
  selector: 'pngx-mail-account-edit-dialog',
  templateUrl: './mail-account-edit-dialog.component.html',
  styleUrls: ['./mail-account-edit-dialog.component.scss'],
  imports: [
    TextComponent,
    CheckComponent,
    PasswordComponent,
    SelectComponent,
    FormsModule,
    ReactiveFormsModule,
    NgbAlertModule,
  ],
})
export class MailAccountEditDialogComponent
  extends EditDialogComponent<MailAccount>
  implements OnInit
{
  testActive: boolean = false
  readonly testResult = signal<string>(undefined)
  alertTimeout

  @ViewChild('testResultAlert', { static: false }) testResultAlert: NgbAlert

  constructor() {
    super()
    this.service = inject(MailAccountService)
    this.userService = inject(UserService)
    this.settingsService = inject(SettingsService)
  }

  ngOnInit(): void {
    // Subscribing *after* super.ngOnInit() is load-bearing: the base class
    // patches a saved account into the form there, which emits on
    // imap_security. Subscribing first would read that as a user edit and
    // rewrite a stored port.
    super.ngOnInit()

    const security = this.objectForm.get('imap_security')
    security.valueChanges
      .pipe(
        startWith(security.value),
        pairwise(),
        takeUntil(this.unsubscribeNotifier)
      )
      .subscribe(([previous, current]: [IMAPSecurity, IMAPSecurity]) => {
        const portField = this.objectForm.get('imap_port')
        const port = portField.value
        const isUnset =
          port === null || port === undefined || String(port).trim() === ''
        // Follow the security setting only while the port is still whatever we
        // last put there; once the user has customised it, it is theirs.
        if (isUnset || Number(port) === IMAP_DEFAULT_PORTS[previous]) {
          portField.setValue(IMAP_DEFAULT_PORTS[current])
        }
      })
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
      imap_port: new FormControl(IMAP_DEFAULT_PORTS[DEFAULT_IMAP_SECURITY]),
      imap_security: new FormControl(DEFAULT_IMAP_SECURITY),
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
    this.testResult.set(null)
    clearTimeout(this.alertTimeout)
    const mailService = this.service as MailAccountService
    const newObject = Object.assign(
      Object.assign({}, this.object),
      this.objectForm.value
    )
    mailService.test(newObject).subscribe({
      next: (result: { success: boolean }) => {
        this.testActive = false
        this.testResult.set(result.success ? 'success' : 'danger')
        this.alertTimeout = setTimeout(() => this.testResultAlert.close(), 5000)
      },
      error: (e) => {
        this.testActive = false
        this.testResult.set('danger')
        this.alertTimeout = setTimeout(() => this.testResultAlert.close(), 5000)
        this.error = e.error
      },
    })
  }

  get testResultMessage() {
    return this.testResult() === 'success'
      ? $localize`Successfully connected to the mail server`
      : $localize`Unable to connect to the mail server`
  }
}
