import { Component, OnDestroy, OnInit } from '@angular/core'
import { ActivatedRoute } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject, delay, first, takeUntil, tap } from 'rxjs'
import { MailAccount, MailAccountType } from 'src/app/data/mail-account'
import { MailRule } from 'src/app/data/mail-rule'
import { ObjectWithPermissions } from 'src/app/data/object-with-permissions'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import {
  PermissionAction,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { AbstractPaperlessService } from 'src/app/services/rest/abstract-paperless-service'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'
import { MailRuleService } from 'src/app/services/rest/mail-rule.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { MailAccountEditDialogComponent } from '../../common/edit-dialog/mail-account-edit-dialog/mail-account-edit-dialog.component'
import { MailRuleEditDialogComponent } from '../../common/edit-dialog/mail-rule-edit-dialog/mail-rule-edit-dialog.component'
import { PermissionsDialogComponent } from '../../common/permissions-dialog/permissions-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'

@Component({
  selector: 'pngx-mail',
  templateUrl: './mail.component.html',
  styleUrls: ['./mail.component.scss'],
})
export class MailComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  public MailAccountType = MailAccountType

  mailAccounts: MailAccount[] = []
  mailRules: MailRule[] = []

  unsubscribeNotifier: Subject<any> = new Subject()
  oAuthAccountId: number

  public get gmailOAuthUrl(): string {
    return this.settingsService.get(SETTINGS_KEYS.GMAIL_OAUTH_URL)
  }

  public get outlookOAuthUrl(): string {
    return this.settingsService.get(SETTINGS_KEYS.OUTLOOK_OAUTH_URL)
  }

  public loadingRules: boolean = true
  public showRules: boolean = false
  public loadingAccounts: boolean = true
  public showAccounts: boolean = false

  constructor(
    public mailAccountService: MailAccountService,
    public mailRuleService: MailRuleService,
    private toastService: ToastService,
    private modalService: NgbModal,
    public permissionsService: PermissionsService,
    private settingsService: SettingsService,
    private route: ActivatedRoute
  ) {
    super()
  }

  ngOnInit(): void {
    this.mailAccountService
      .listAll(null, null, { full_perms: true })
      .pipe(
        first(),
        takeUntil(this.unsubscribeNotifier),
        tap((r) => {
          this.mailAccounts = r.results
          if (this.oAuthAccountId) {
            this.editMailAccount(
              this.mailAccounts.find(
                (account) => account.id === this.oAuthAccountId
              )
            )
          }
        }),
        delay(100)
      )
      .subscribe({
        next: () => {
          this.loadingAccounts = false
          this.showAccounts = true
        },
        error: (e) => {
          this.toastService.showError(
            $localize`Error retrieving mail accounts`,
            e
          )
        },
      })

    this.mailRuleService
      .listAll(null, null, { full_perms: true })
      .pipe(
        first(),
        takeUntil(this.unsubscribeNotifier),
        tap((r) => {
          this.mailRules = r.results
        }),
        delay(100)
      )
      .subscribe({
        next: (r) => {
          this.loadingRules = false
          this.showRules = true
        },
        error: (e) => {
          this.toastService.showError($localize`Error retrieving mail rules`, e)
        },
      })

    this.route.queryParamMap.subscribe((params) => {
      if (params.get('oauth_success')) {
        const success = params.get('oauth_success') === '1'
        if (success) {
          this.toastService.showInfo($localize`OAuth2 authentication success`)
          this.oAuthAccountId = parseInt(params.get('account_id'))
          if (this.mailAccounts.length > 0) {
            this.editMailAccount(
              this.mailAccounts.find(
                (account) => account.id === this.oAuthAccountId
              )
            )
          }
        } else {
          this.toastService.showError(
            $localize`OAuth2 authentication failed, see logs for details`
          )
        }
      }
    })
  }

  ngOnDestroy() {
    this.unsubscribeNotifier.next(true)
  }

  editMailAccount(account: MailAccount = null) {
    const modal = this.modalService.open(MailAccountEditDialogComponent, {
      backdrop: 'static',
      size: 'xl',
    })
    modal.componentInstance.dialogMode = account
      ? EditDialogMode.EDIT
      : EditDialogMode.CREATE
    modal.componentInstance.object = account
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newMailAccount) => {
        this.toastService.showInfo(
          $localize`Saved account "${newMailAccount.name}".`
        )
        this.mailAccountService.clearCache()
        this.mailAccountService
          .listAll(null, null, { full_perms: true })
          .subscribe((r) => {
            this.mailAccounts = r.results
          })
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving account.`, e)
      })
  }

  deleteMailAccount(account: MailAccount) {
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete mail account`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete this mail account.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.mailAccountService.delete(account).subscribe({
        next: () => {
          modal.close()
          this.toastService.showInfo($localize`Deleted mail account`)
          this.mailAccountService.clearCache()
          this.mailAccountService
            .listAll(null, null, { full_perms: true })
            .subscribe((r) => {
              this.mailAccounts = r.results
            })
        },
        error: (e) => {
          this.toastService.showError(
            $localize`Error deleting mail account.`,
            e
          )
        },
      })
    })
  }

  processAccount(account: MailAccount) {
    this.mailAccountService.processAccount(account).subscribe({
      next: () => {
        this.toastService.showInfo($localize`Processing mail account`)
      },
      error: (e) => {
        this.toastService.showError($localize`Error processing mail account`, e)
      },
    })
  }

  editMailRule(rule: MailRule = null, forceCreate = false) {
    const modal = this.modalService.open(MailRuleEditDialogComponent, {
      backdrop: 'static',
      size: 'xl',
    })
    modal.componentInstance.dialogMode =
      rule && !forceCreate ? EditDialogMode.EDIT : EditDialogMode.CREATE
    modal.componentInstance.object = rule
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newMailRule) => {
        this.toastService.showInfo($localize`Saved rule "${newMailRule.name}".`)
        this.mailRuleService.clearCache()
        this.mailRuleService
          .listAll(null, null, { full_perms: true })
          .subscribe((r) => {
            this.mailRules = r.results
          })
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving rule.`, e)
      })
  }

  copyMailRule(rule: MailRule) {
    const clone = { ...rule }
    clone.id = null
    clone.name = `${rule.name} (copy)`
    this.editMailRule(clone, true)
  }

  onMailRuleEnableToggled(rule: MailRule) {
    this.mailRuleService.patch(rule).subscribe({
      next: () => {
        this.toastService.showInfo(
          rule.enabled
            ? $localize`Rule "${rule.name}" enabled.`
            : $localize`Rule "${rule.name}" disabled.`
        )
      },
      error: (e) => {
        this.toastService.showError($localize`Error toggling rule.`, e)
      },
    })
  }

  deleteMailRule(rule: MailRule) {
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete mail rule`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete this mail rule.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.mailRuleService.delete(rule).subscribe({
        next: () => {
          modal.close()
          this.toastService.showInfo($localize`Deleted mail rule`)
          this.mailRuleService.clearCache()
          this.mailRuleService
            .listAll(null, null, { full_perms: true })
            .subscribe((r) => {
              this.mailRules = r.results
            })
        },
        error: (e) => {
          this.toastService.showError($localize`Error deleting mail rule.`, e)
        },
      })
    })
  }

  editPermissions(object: MailRule | MailAccount) {
    const modal = this.modalService.open(PermissionsDialogComponent, {
      backdrop: 'static',
    })
    const dialog: PermissionsDialogComponent =
      modal.componentInstance as PermissionsDialogComponent
    dialog.object = object
    modal.componentInstance.confirmClicked.subscribe(
      ({ permissions, merge }) => {
        modal.componentInstance.buttonsEnabled = false
        const service: AbstractPaperlessService<MailRule | MailAccount> =
          'account' in object ? this.mailRuleService : this.mailAccountService
        object.owner = permissions['owner']
        object['set_permissions'] = permissions['set_permissions']
        service.patch(object).subscribe({
          next: () => {
            this.toastService.showInfo($localize`Permissions updated`)
            modal.close()
          },
          error: (e) => {
            this.toastService.showError(
              $localize`Error updating permissions`,
              e
            )
          },
        })
      }
    )
  }

  userCanEdit(obj: ObjectWithPermissions): boolean {
    return this.permissionsService.currentUserHasObjectPermissions(
      PermissionAction.Change,
      obj
    )
  }

  userIsOwner(obj: ObjectWithPermissions): boolean {
    return this.permissionsService.currentUserOwnsObject(obj)
  }
}
