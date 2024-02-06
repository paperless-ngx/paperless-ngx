import { Component, OnDestroy, OnInit } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { ProfileService } from 'src/app/services/profile.service'
import { SocialAccount, SocialAccountProvider } from 'src/app/data/user-profile'
import { ToastService } from 'src/app/services/toast.service'
import { Subject, takeUntil } from 'rxjs'
import { Clipboard } from '@angular/cdk/clipboard'

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
    auth_token: new FormControl(''),
  })

  private currentPassword: string
  private newPassword: string
  private passwordConfirm: string
  public showPasswordConfirm: boolean = false
  public hasUsablePassword: boolean = false

  private currentEmail: string
  private newEmail: string
  private emailConfirm: string
  public showEmailConfirm: boolean = false

  public copied: boolean = false

  public socialAccounts: SocialAccount[] = []
  public socialAccountProviders: SocialAccountProvider[] = []

  constructor(
    private profileService: ProfileService,
    public activeModal: NgbActiveModal,
    private toastService: ToastService,
    private clipboard: Clipboard
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
        this.hasUsablePassword = profile.has_usable_password
        this.form.get('password').valueChanges.subscribe((newPassword) => {
          this.newPassword = newPassword
          this.onPasswordChange()
        })
        this.socialAccounts = profile.social_accounts
      })

    this.profileService
      .getSocialAccountProviders()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((providers) => {
        this.socialAccountProviders = providers
      })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }

  get saveDisabled(): boolean {
    return this.error?.password_confirm || this.error?.email_confirm
  }

  onEmailKeyUp(event: KeyboardEvent): void {
    this.newEmail = (event.target as HTMLInputElement)?.value
    this.onEmailChange()
  }

  onEmailConfirmKeyUp(event: KeyboardEvent): void {
    this.emailConfirm = (event.target as HTMLInputElement)?.value
    this.onEmailChange()
  }

  onEmailChange(): void {
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

  onPasswordKeyUp(event: KeyboardEvent): void {
    if ((event.target as HTMLElement).tagName !== 'input') return // toggle button can trigger this handler
    this.newPassword = (event.target as HTMLInputElement)?.value
    this.onPasswordChange()
  }

  onPasswordConfirmKeyUp(event: KeyboardEvent): void {
    this.passwordConfirm = (event.target as HTMLInputElement)?.value
    this.onPasswordChange()
  }

  onPasswordChange(): void {
    this.showPasswordConfirm = this.currentPassword !== this.newPassword

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

  save(): void {
    const passwordChanged =
      this.newPassword && this.currentPassword !== this.newPassword
    const profile = Object.assign({}, this.form.value)
    this.networkActive = true
    this.profileService
      .update(profile)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: () => {
          this.toastService.showInfo($localize`Profile updated successfully`)
          if (passwordChanged) {
            this.toastService.showInfo(
              $localize`Password has been changed, you will be logged out momentarily.`
            )
            setTimeout(() => {
              window.location.href = `${window.location.origin}/accounts/logout/?next=/accounts/login/?next=/`
            }, 2500)
          }
          this.activeModal.close()
        },
        error: (error) => {
          this.toastService.showError($localize`Error saving profile`, error)
          this.networkActive = false
        },
      })
  }

  cancel(): void {
    this.activeModal.close()
  }

  generateAuthToken(): void {
    this.profileService.generateAuthToken().subscribe({
      next: (token: string) => {
        this.form.patchValue({ auth_token: token })
      },
      error: (error) => {
        this.toastService.showError(
          $localize`Error generating auth token`,
          error
        )
      },
    })
  }

  copyAuthToken(): void {
    this.clipboard.copy(this.form.get('auth_token').value)
    this.copied = true
    setTimeout(() => {
      this.copied = false
    }, 3000)
  }

  disconnectSocialAccount(id: number): void {
    this.profileService
      .disconnectSocialAccount(id)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (id: number) => {
          this.socialAccounts = this.socialAccounts.filter((a) => a.id != id)
        },
        error: (error) => {
          this.toastService.showError(
            $localize`Error disconnecting social account`,
            error
          )
        },
      })
  }
}
