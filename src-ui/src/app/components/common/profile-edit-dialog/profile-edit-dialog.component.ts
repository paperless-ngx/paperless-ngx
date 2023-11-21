import { Component, OnDestroy, OnInit } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { ProfileService } from 'src/app/services/profile.service'
import { ToastService } from 'src/app/services/toast.service'
import { Subject, takeUntil } from 'rxjs'

@Component({
  selector: 'pngx-profile-edit-dialog',
  templateUrl: './profile-edit-dialog.component.html',
  styleUrls: ['./profile-edit-dialog.component.scss'],
})
export class ProfileEditDialogComponent implements OnInit, OnDestroy {
  public networkActive: boolean = false
  public error: any
  private unsubscribeNotifier: Subject<any> = new Subject()

  public form = new FormGroup({
    email: new FormControl(''),
    email_confirm: new FormControl({ value: null, disabled: true }),
    password: new FormControl(null),
    password_confirm: new FormControl({ value: null, disabled: true }),
    first_name: new FormControl(''),
    last_name: new FormControl(''),
  })

  private currentPassword: string
  private newPassword: string
  private passwordConfirm: string
  public showPasswordConfirm: boolean = false

  private currentEmail: string
  private newEmail: string
  private emailConfirm: string
  public showEmailConfirm: boolean = false

  constructor(
    private profileService: ProfileService,
    public activeModal: NgbActiveModal,
    private toastService: ToastService
  ) {}

  ngOnInit(): void {
    this.networkActive = true
    this.profileService
      .get()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((profile) => {
        this.networkActive = false
        this.form.patchValue(profile)
        this.currentEmail = profile.email
        this.form.get('email').valueChanges.subscribe((newEmail) => {
          this.newEmail = newEmail
          this.onEmailChange()
        })
        this.currentPassword = profile.password
        this.form.get('password').valueChanges.subscribe((newPassword) => {
          this.newPassword = newPassword
          this.onPasswordChange()
        })
      })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }

  get saveDisabled(): boolean {
    return this.error?.password_confirm || this.error?.email_confirm
  }

  onEmailKeyUp(event: KeyboardEvent) {
    this.newEmail = (event.target as HTMLInputElement)?.value
    this.onEmailChange()
  }

  onEmailConfirmKeyUp(event: KeyboardEvent) {
    this.emailConfirm = (event.target as HTMLInputElement)?.value
    this.onEmailChange()
  }

  onEmailChange() {
    this.showEmailConfirm = this.currentEmail !== this.newEmail
    if (this.showEmailConfirm) {
      this.form.get('email_confirm').enable()
      if (this.newEmail !== this.emailConfirm) {
        if (!this.error) this.error = {}
        this.error.email_confirm = $localize`Emails must match`
      } else {
        delete this.error?.email_confirm
      }
    } else {
      this.form.get('email_confirm').disable()
      delete this.error?.email_confirm
    }
  }

  onPasswordKeyUp(event: KeyboardEvent) {
    this.newPassword = (event.target as HTMLInputElement)?.value
    this.onPasswordChange()
  }

  onPasswordConfirmKeyUp(event: KeyboardEvent) {
    this.passwordConfirm = (event.target as HTMLInputElement)?.value
    this.onPasswordChange()
  }

  onPasswordChange() {
    this.showPasswordConfirm = this.currentPassword !== this.newPassword
    console.log(this.currentPassword, this.newPassword, this.passwordConfirm)

    if (this.showPasswordConfirm) {
      this.form.get('password_confirm').enable()
      if (this.newPassword !== this.passwordConfirm) {
        if (!this.error) this.error = {}
        this.error.password_confirm = $localize`Passwords must match`
      } else {
        delete this.error?.password_confirm
      }
    } else {
      this.form.get('password_confirm').disable()
      delete this.error?.password_confirm
    }
  }

  save() {
    const profile = Object.assign({}, this.form.value)
    this.networkActive = true
    this.profileService
      .update(profile)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: () => {
          this.toastService.showInfo($localize`Profile updated successfully`)
          this.activeModal.close()
        },
        error: (error) => {
          this.toastService.showError($localize`Error saving profile`, error)
          this.networkActive = false
        },
      })
  }

  cancel() {
    this.activeModal.close()
  }
}
