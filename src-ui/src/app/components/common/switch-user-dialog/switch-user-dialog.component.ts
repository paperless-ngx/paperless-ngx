import { Component, OnInit, inject, signal } from '@angular/core'
import { NgbActiveModal, NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Observable, filter, finalize, first, switchMap } from 'rxjs'
import {
  AccountSessionRedirect,
  AccountSessionUser,
} from 'src/app/data/user-profile'
import { IdentityChangeService } from 'src/app/services/identity-change.service'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import { ProfileService } from 'src/app/services/profile.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../confirm-dialog/confirm-dialog.component'

@Component({
  selector: 'pngx-switch-user-dialog',
  templateUrl: './switch-user-dialog.component.html',
  styleUrls: ['./switch-user-dialog.component.scss'],
  imports: [NgxBootstrapIconsModule],
})
export class SwitchUserDialogComponent implements OnInit {
  readonly activeModal = inject(NgbActiveModal)
  private readonly modalService = inject(NgbModal)
  private readonly profileService = inject(ProfileService)
  private readonly openDocumentsService = inject(OpenDocumentsService)
  private readonly identityChangeService = inject(IdentityChangeService)
  private readonly toastService = inject(ToastService)

  readonly accounts = signal<AccountSessionUser[]>([])
  readonly enabled = signal(true)
  readonly loading = signal(true)

  /** Loads the enrolled accounts when the dialog opens. */
  ngOnInit(): void {
    this.reload()
  }

  /** Returns the most useful available label for an account. */
  displayName(account: AccountSessionUser): string {
    const fullName =
      `${account.first_name ?? ''} ${account.last_name ?? ''}`.trim()
    return fullName || account.username
  }

  /** Activates the selected enrolled account. */
  switchAccount(account: AccountSessionUser): void {
    if (account.current || this.loading()) return
    this.runIdentityChange(() =>
      this.profileService.switchAccountSession(account.id)
    )
  }

  /** Starts the authentication flow for enrolling another account. */
  addAccount(): void {
    if (this.loading()) return
    this.runIdentityChange(() => this.profileService.addAccountSession())
  }

  /** Confirms and removes an account from quick switching. */
  removeAccount(event: Event, account: AccountSessionUser): void {
    event.stopPropagation()
    if (this.loading()) return

    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Remove account`
    modal.componentInstance.messageBold = account.current
      ? $localize`This will log out the current account.`
      : $localize`This will log out this saved account.`
    modal.componentInstance.message = $localize`You will need to sign in again before it can be used for quick switching.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Remove account`
    modal.componentInstance.confirmClicked.pipe(first()).subscribe(() => {
      modal.close()
      if (account.current) {
        this.runIdentityChange(() =>
          this.profileService.removeAccountSession(account.id)
        )
      } else {
        this.loading.set(true)
        this.profileService
          .removeAccountSession(account.id)
          .pipe(finalize(() => this.loading.set(false)))
          .subscribe({
            next: () => this.reload(),
            error: (error) =>
              this.toastService.showError(
                $localize`Unable to remove the account.`,
                error
              ),
          })
      }
    })
  }

  /** Confirms and logs out every enrolled account. */
  logoutAll(): void {
    if (this.loading()) return
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Log out all accounts`
    modal.componentInstance.messageBold = $localize`All accounts saved for quick switching will be logged out.`
    modal.componentInstance.message = $localize`You will need to sign in again to use them.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Log out all`
    modal.componentInstance.confirmClicked.pipe(first()).subscribe(() => {
      modal.close()
      this.runIdentityChange(() =>
        this.profileService.logoutAllAccountSessions()
      )
    })
  }

  /** Refreshes the quick-switch account list. */
  private reload(): void {
    this.loading.set(true)
    this.profileService
      .getAccountSessions()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (response) => {
          this.enabled.set(response.enabled)
          this.accounts.set(response.accounts)
        },
        error: (error) =>
          this.toastService.showError(
            $localize`Unable to load available accounts.`,
            error
          ),
      })
  }

  /** Closes open documents before performing an identity-changing request. */
  private runIdentityChange(
    request: () => Observable<AccountSessionRedirect>
  ): void {
    this.openDocumentsService
      .closeAll()
      .pipe(
        first(),
        filter((confirmed) => confirmed),
        switchMap(() => {
          this.loading.set(true)
          return request()
        }),
        finalize(() => this.loading.set(false))
      )
      .subscribe({
        next: (response) => {
          this.activeModal.close()
          this.identityChangeService.finish(response.redirect_url)
        },
        error: (error) =>
          this.toastService.showError(
            $localize`Unable to change the active account.`,
            error
          ),
      })
  }
}
