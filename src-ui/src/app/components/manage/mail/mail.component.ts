import { Component, OnInit, OnDestroy } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject, first, takeUntil } from 'rxjs'
import { ObjectWithPermissions } from 'src/app/data/object-with-permissions'
import { MailAccount } from 'src/app/data/mail-account'
import { MailRule } from 'src/app/data/mail-rule'
import {
  PermissionsService,
  PermissionAction,
} from 'src/app/services/permissions.service'
import { AbstractPaperlessService } from 'src/app/services/rest/abstract-paperless-service'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'
import { MailRuleService } from 'src/app/services/rest/mail-rule.service'
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
  mailAccounts: MailAccount[] = []
  mailRules: MailRule[] = []

  unsubscribeNotifier: Subject<any> = new Subject()

  constructor(
    public mailAccountService: MailAccountService,
    public mailRuleService: MailRuleService,
    private toastService: ToastService,
    private modalService: NgbModal,
    public permissionsService: PermissionsService
  ) {
    super()
  }

  ngOnInit(): void {
    this.mailAccountService
      .listAll(null, null, { full_perms: true })
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (r) => {
          this.mailAccounts = r.results
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
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (r) => {
          this.mailRules = r.results
        },
        error: (e) => {
          this.toastService.showError($localize`Error retrieving mail rules`, e)
        },
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

  editMailRule(rule: MailRule = null) {
    const modal = this.modalService.open(MailRuleEditDialogComponent, {
      backdrop: 'static',
      size: 'xl',
    })
    modal.componentInstance.dialogMode = rule
      ? EditDialogMode.EDIT
      : EditDialogMode.CREATE
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
